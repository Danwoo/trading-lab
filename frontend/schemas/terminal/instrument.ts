// schemas/terminal/instrument.ts

/** 백엔드 `instrument_schema.py` 의 `InstrumentOut`. */
export interface InstrumentOut {
  country: string;
  market: string;
  symbol: string;
  issuer_nm: string;
  currency: string;
  is_active: string;
}

/**
 * `unavailable_reason` 이 0건과 짝을 이룬다 — 검색 결과 0건이 「그런 종목이 없다」인지
 * 「마스터를 아직 안 받았다」인지 화면이 구분할 수 있어야 한다(FR-021).
 */
export interface InstrumentsOut {
  items: InstrumentOut[];
  total_count: number;
  unavailable_reason: string | null;
}
