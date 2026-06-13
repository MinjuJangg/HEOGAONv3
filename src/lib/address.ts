const KAKAO_JS_KEY = process.env.NEXT_PUBLIC_KAKAO_JS_KEY || "";
const DATA_GO_KR_KEY = process.env.NEXT_PUBLIC_DATA_GO_KR_SERVICE_KEY || "";
const API_BASE_URL = (process.env.NEXT_PUBLIC_HEOGAON_API_BASE_URL || "http://127.0.0.1:4100").replace(/\/$/, "");
const BUILDING_BASE_URL = "https://apis.data.go.kr/1613000/BldRgstHubService";

const BUILDING_OPERATIONS = {
  title: "getBrTitleInfo",
  floor: "getBrFlrOulnInfo",
  unit: "getBrExposPubuseAreaInfo",
  landZone: "getBrJijiguInfo",
} as const;

export interface AddressResult {
  label: string;
  roadAddress: string;
  jibunAddress: string;
  buildingName: string;
  zoneNo: string;
  buildingParams: BuildingParams | null;
}

export interface BuildingParams {
  sigunguCd: string;
  bjdongCd: string;
  platGbCd: string;
  bun: string;
  ji: string;
}

export interface ResolvedAddress {
  roadAddress: string;
  jibunAddress: string;
  buildingParams: BuildingParams | null;
}

export interface BuildingLedgerRaw {
  buildingParams: BuildingParams;
  records: {
    title: unknown[];
    floor: unknown[];
    unit: unknown[];
    landZone: unknown[];
  };
}

interface KakaoAddress {
  b_code?: string;
  main_address_no?: string;
  sub_address_no?: string;
  mountain_yn?: string;
  address_name?: string;
}

interface KakaoRoadAddress {
  address_name?: string;
  building_name?: string;
  zone_no?: string;
}

interface KakaoGeocodeItem {
  address_name: string;
  address?: KakaoAddress;
  road_address?: KakaoRoadAddress | null;
}

type KakaoStatus = "OK" | "ZERO_RESULT" | "ERROR";

declare global {
  interface Window {
    kakao?: {
      maps: {
        load: (callback: () => void) => void;
        services: {
          Geocoder: new () => {
            addressSearch: (
              query: string,
              callback: (result: KakaoGeocodeItem[], status: KakaoStatus) => void,
              options?: { size?: number },
            ) => void;
          };
          Status: { OK: KakaoStatus };
        };
      };
    };
  }
}

let sdkPromise: Promise<void> | null = null;

export function loadKakaoSdk(): Promise<void> {
  if (typeof window === "undefined") return Promise.reject(new Error("브라우저 환경에서만 주소 검색을 사용할 수 있어요."));
  if (window.kakao?.maps?.services) return Promise.resolve();
  if (sdkPromise) return sdkPromise;
  if (!KAKAO_JS_KEY) return Promise.reject(new Error("NEXT_PUBLIC_KAKAO_JS_KEY가 설정되지 않았어요."));

  sdkPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = `https://dapi.kakao.com/v2/maps/sdk.js?appkey=${KAKAO_JS_KEY}&libraries=services&autoload=false`;
    script.async = true;
    script.onload = () => window.kakao?.maps.load(() => resolve());
    script.onerror = () => reject(new Error("카카오 주소 검색 스크립트를 불러오지 못했어요."));
    document.head.appendChild(script);
  });

  return sdkPromise;
}

function toBuildingParams(address?: KakaoAddress): BuildingParams | null {
  const bcode = address?.b_code || "";
  const main = String(address?.main_address_no || "").trim();

  if (bcode.length < 10 || !main) return null;

  return {
    sigunguCd: bcode.slice(0, 5),
    bjdongCd: bcode.slice(5, 10),
    platGbCd: address?.mountain_yn === "Y" ? "1" : "0",
    bun: main.padStart(4, "0"),
    ji: String(address?.sub_address_no || "0").trim().padStart(4, "0"),
  };
}

export async function searchAddress(query: string): Promise<AddressResult[]> {
  const keyword = query.trim();
  if (!keyword) return [];

  try {
    await loadKakaoSdk();
  } catch {
    return searchAddressFromBackend(keyword);
  }

  return new Promise<AddressResult[]>((resolve) => {
    const geocoder = new window.kakao!.maps.services.Geocoder();
    geocoder.addressSearch(
      keyword,
      (items, status) => {
        if (status !== window.kakao!.maps.services.Status.OK || !items) {
          resolve([]);
          return;
        }

        resolve(
          items.map((item) => ({
            label: item.road_address?.address_name || item.address_name,
            roadAddress: item.road_address?.address_name || "",
            jibunAddress: item.address?.address_name || item.address_name,
            buildingName: item.road_address?.building_name || "",
            zoneNo: item.road_address?.zone_no || "",
            buildingParams: toBuildingParams(item.address),
          })),
        );
      },
      { size: 10 },
    );
  });
}

async function searchAddressFromBackend(keyword: string): Promise<AddressResult[]> {
  const response = await fetch(`${API_BASE_URL}/api/address/search?query=${encodeURIComponent(keyword)}`);
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `주소 검색 API 오류: HTTP ${response.status}`);
  }
  const payload = (await response.json()) as { results?: AddressResult[] };
  return Array.isArray(payload.results) ? payload.results : [];
}

function responseItems(payload: unknown): unknown[] {
  const body = (payload as { response?: { body?: { items?: { item?: unknown } } } })?.response?.body;
  const item = body?.items?.item;
  if (!item) return [];
  return Array.isArray(item) ? item : [item];
}

async function fetchOperation(operation: keyof typeof BUILDING_OPERATIONS, params: BuildingParams): Promise<unknown[]> {
  const query = new URLSearchParams({
    serviceKey: DATA_GO_KR_KEY,
    _type: "json",
    numOfRows: "100",
    pageNo: "1",
    sigunguCd: params.sigunguCd,
    bjdongCd: params.bjdongCd,
    platGbCd: params.platGbCd,
    bun: params.bun,
    ji: params.ji,
  });
  const response = await fetch(`${BUILDING_BASE_URL}/${BUILDING_OPERATIONS[operation]}?${query.toString()}`);

  if (!response.ok) throw new Error(`건축물대장 ${operation} 조회 실패: HTTP ${response.status}`);

  const payload = await response.json();
  const header = (payload as { response?: { header?: { resultCode?: string; resultMsg?: string } } })?.response?.header;
  if (header?.resultCode && header.resultCode !== "00") {
    throw new Error(`건축물대장 ${operation} 오류: ${header.resultMsg || header.resultCode}`);
  }

  return responseItems(payload);
}

export async function fetchBuildingLedger(params: BuildingParams): Promise<BuildingLedgerRaw> {
  if (!DATA_GO_KR_KEY) throw new Error("NEXT_PUBLIC_DATA_GO_KR_SERVICE_KEY가 설정되지 않았어요.");

  const [title, floor, unit, landZone] = await Promise.all([
    fetchOperation("title", params),
    fetchOperation("floor", params),
    fetchOperation("unit", params),
    fetchOperation("landZone", params),
  ]);

  return { buildingParams: params, records: { title, floor, unit, landZone } };
}
