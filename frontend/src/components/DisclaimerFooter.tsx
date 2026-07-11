/** 면책 고지 (AC10, C3). 참고용 — 실제 항해/입수 판단 근거 아님. */
export function DisclaimerFooter() {
  return (
    <footer className="disclaimer">
      ⚠️ 본 서비스는 <b>참고용</b>이며 실제 항해·조업·입수 판단의 공식 근거가 아닙니다. 위험도
      임계값은 공식 기상특보 기준을 뼈대로 한 해커톤급 매핑입니다. 실제 활동 전 기상청·해양경찰청
      공식 정보를 확인하세요.
      <span className="disclaimer-src">
        데이터: KHOA 바다누리 · 기상청 (공공누리, 출처표시) · 오픈소스 MIT
      </span>
    </footer>
  );
}
