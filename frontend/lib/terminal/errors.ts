/** 백엔드 계약이 아직 확정되지 않은 엔드포인트를 표현한다 (FE-AD-13). 데이터 훅이 이를 잡아 provenance.placeholder 로 바꾼다. */
export class EndpointNotReadyError extends Error {
  readonly endpoint: string;

  constructor(endpoint: string) {
    super(`엔드포인트가 아직 준비되지 않았습니다: ${endpoint}`);
    this.name = "EndpointNotReadyError";
    this.endpoint = endpoint;
  }
}
