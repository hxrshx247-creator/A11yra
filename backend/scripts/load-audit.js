import http from "k6/http";
import { check } from "k6";
import { Rate } from "k6/metrics";

const successes = new Rate("successful_audits");
const bytes = open("../fixtures/pilot-syllabus.docx", "b");
const mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
const base = __ENV.A11YRA_BASE_URL || "http://127.0.0.1:5173";

export const options = {
  scenarios: {
    audit: { executor: "shared-iterations", vus: 2, iterations: 10, maxDuration: "30s" },
  },
  thresholds: { successful_audits: ["rate==1"], http_req_duration: ["p(95)<1500"] },
};

export default function () {
  if (!__ENV.A11YRA_API_KEY) throw new Error("Set A11YRA_API_KEY to a fresh Institution demo key.");
  const response = http.post(`${base}/api/public/v1/audit`, {
    file: http.file(bytes, "pilot-syllabus.docx", mime),
  }, { headers: { Authorization: `Bearer ${__ENV.A11YRA_API_KEY}` } });
  successes.add(check(response, {
    "returned audit JSON": (result) => result.status === 200 && result.json("progress.passed") === 2,
  }));
}
