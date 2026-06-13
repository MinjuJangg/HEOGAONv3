import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/common/Icon";
import {
  fetchBuildingLedger,
  searchAddress,
  type AddressResult,
  type BuildingLedgerRaw,
  type ResolvedAddress,
} from "@/lib/address";
import type { SlotQuestionView as SlotQuestionViewModel } from "@/types/flow";

export function AddressSearchView({
  view,
  onResolved,
  onClear,
  onUnknown,
}: {
  view: SlotQuestionViewModel;
  onResolved: (address: ResolvedAddress, building: BuildingLedgerRaw | null) => void;
  onClear: () => void;
  onUnknown: () => void;
}) {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<AddressResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState<AddressResult | null>(null);
  const [loadingBuilding, setLoadingBuilding] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [noBuilding, setNoBuilding] = useState(false);
  const [error, setError] = useState("");
  const debounceRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (debounceRef.current) window.clearTimeout(debounceRef.current);
    };
  }, []);

  function runSearch(keyword: string) {
    if (debounceRef.current) window.clearTimeout(debounceRef.current);

    if (!keyword.trim()) {
      setResults([]);
      setSearched(false);
      return;
    }

    debounceRef.current = window.setTimeout(async () => {
      setSearching(true);
      setError("");
      try {
        setResults(await searchAddress(keyword));
      } catch (err) {
        setError(err instanceof Error ? err.message : "주소 검색에 실패했어요.");
        setResults([]);
      } finally {
        setSearching(false);
        setSearched(true);
      }
    }, 300);
  }

  function onChangeQuery(value: string) {
    setQuery(value);
    setSelected(null);
    setConfirmed(false);
    setNoBuilding(false);
    onClear();
    runSearch(value);
  }

  async function selectResult(result: AddressResult) {
    setSelected(result);
    setResults([]);
    setSearched(false);
    setQuery(result.label);
    setConfirmed(false);
    setNoBuilding(false);
    setError("");

    const address: ResolvedAddress = {
      roadAddress: result.roadAddress || result.label,
      jibunAddress: result.jibunAddress,
      buildingParams: result.buildingParams,
    };

    if (!result.buildingParams) {
      setNoBuilding(true);
      setConfirmed(true);
      onResolved(address, null);
      return;
    }

    setLoadingBuilding(true);
    try {
      const building = await fetchBuildingLedger(result.buildingParams);
      onResolved(address, building);
      setConfirmed(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "건축물대장 조회에 실패했어요.");
      onResolved(address, null);
      setConfirmed(true);
      setNoBuilding(true);
    } finally {
      setLoadingBuilding(false);
    }
  }

  const showEmpty = searched && !searching && results.length === 0 && !selected && query.trim().length > 0;

  return (
    <section className="question-card">
      <h1 className="question-title">{view.title}</h1>
      {view.subtitle ? <p className="question-sub">{view.subtitle}</p> : null}
      {view.validationMessage ? <p className="collect-status error-text" role="alert">{view.validationMessage}</p> : null}

      <div className="address-search">
        <div className="address-search-field">
          <span className="address-search-icon" aria-hidden="true"><Icon name="search" size={18} /></span>
          <input
            className="address-search-input"
            type="text"
            value={query}
            onChange={(event) => onChangeQuery(event.target.value)}
            placeholder="도로명 또는 지번 주소를 검색해 주세요"
            autoComplete="off"
            aria-label="주소 검색"
          />
          {searching ? <span className="address-search-spinner" aria-hidden="true" /> : null}
        </div>

        {error ? <p className="collect-status error-text" role="alert">{error}</p> : null}

        {results.length > 0 ? (
          <ul className="address-result-list" role="listbox" aria-label="주소 검색 결과">
            {results.map((result, index) => (
              <li key={`${result.label}-${index}`}>
                <button className="address-result" type="button" role="option" aria-selected="false" onClick={() => selectResult(result)}>
                  <span className="address-result-main">{result.label}</span>
                  {result.buildingName ? <span className="address-result-sub">{result.buildingName}</span> : null}
                  {result.jibunAddress && result.jibunAddress !== result.label ? (
                    <span className="address-result-zone">{result.jibunAddress}</span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {showEmpty ? (
          <p className="address-search-hint">검색 결과가 없어요. 도로명과 건물번호까지 입력하면 더 정확해요.</p>
        ) : null}

        {selected && loadingBuilding ? (
          <div className="address-confirm pending">
            <span className="address-confirm-icon" aria-hidden="true"><Icon name="search" size={16} /></span>
            <span>건축물대장 정보를 불러오는 중이에요.</span>
          </div>
        ) : null}

        {confirmed && selected ? (
          <div className={`address-confirm ${noBuilding ? "warn" : "done"}`}>
            <span className="address-confirm-icon" aria-hidden="true">
              <Icon name={noBuilding ? "help" : "check"} size={16} />
            </span>
            <span className="address-confirm-text">
              <strong>{selected.roadAddress || selected.label}</strong>
              <em>{noBuilding ? "주소는 선택됐고, 건축물 정보는 다음 단계에서 한 번 더 확인해요." : selected.buildingName || "건축물대장 조회 완료"}</em>
            </span>
          </div>
        ) : null}

        <button className="unknown-inline-button" type="button" onClick={onUnknown}>
          <span className="unknown-inline-icon" aria-hidden="true"><Icon name="help" size={16} /></span>
          <span>아직 정해지지 않았어요</span>
        </button>
      </div>
    </section>
  );
}
