# HEOGAON Precheck Data Layer

This layer is intentionally separate from the frontend. It prepares the data needed for:

- exact address normalization
- BuildingHUB building-register lookup and cache
- main/floor/unit use extraction
- Seoul-wide LOCALDATA permit history lookup by address
- early food-business rule checks such as liquor sales and building-use review

## Sources

- Building register API: `국토교통부_건축HUB_건축물대장정보 서비스`
  - Data portal page: https://www.data.go.kr/data/15134735/openapi.do
  - Used for live title/floor/unit/land-zone attributes.
- Address normalization: road-name address API from `business.juso.go.kr`
  - Used to derive `sigunguCd`, `bjdongCd`, `bun`, `ji`.
- Seoul LOCALDATA CSVs under `data/raw/public_data_csv/seoul`
  - Used for past same-place business/license lookup.

## Build Seoul LOCALDATA Index

Food-related index only:

```powershell
python graph_build\src\build_seoul_precheck_index.py
```

All localdata CSVs:

```powershell
python graph_build\src\build_seoul_precheck_index.py --all
```

Output:

- `data/processed/precheck/seoul_localdata.sqlite`
- `data/processed/precheck/seoul_localdata_summary.json`

## Query Past Same-Place Businesses

```powershell
python graph_build\src\precheck_cli.py query-past-businesses --address "서울특별시 마포구 포은로 63"
```

## BuildingHUB API

Set keys before calling API commands:

```powershell
$env:JUSO_API_KEY="..."
$env:DATA_GO_KR_SERVICE_KEY="..."
```

Normalize address:

```powershell
python graph_build\src\precheck_cli.py normalize-address --address "서울특별시 마포구 포은로 63"
```

Fetch building profile:

```powershell
python graph_build\src\precheck_cli.py building-profile --address "서울특별시 마포구 포은로 63"
```

Compose precheck:

```powershell
python graph_build\src\precheck_cli.py precheck --address "서울특별시 마포구 포은로 63" --business-type 일반음식점영업 --with-building-api
```

Without API keys, omit `--with-building-api`; the command still checks Seoul LOCALDATA history.

