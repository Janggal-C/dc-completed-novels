// 오류 신고 → 구글폼 (줄임말 사전 오류 신고). 응답은 구글 시트에 쌓이고 검수 탭에서 처리
const REPORT_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdxCxj1EoDmLfw13qhHGV90o6kShw62f36EGAfYpBpbflTVCw/formResponse";
const REPORT_FIELDS = {alias: "entry.1363202664", title: "entry.1114325484", url: "entry.995210015", comment: "entry.46682918"};

async function dcnxSendReport({alias = "", title = "", url = "", comment = ""}) {
  const body = new URLSearchParams();
  body.set(REPORT_FIELDS.alias, alias);
  body.set(REPORT_FIELDS.title, title);
  body.set(REPORT_FIELDS.url, url);
  body.set(REPORT_FIELDS.comment, comment);
  // 구글폼은 바깥 제출에 결과를 돌려주지 않음(no-cors) → 네트워크 오류만 잡힘
  await fetch(REPORT_FORM, {method: "POST", mode: "no-cors", body});
}
