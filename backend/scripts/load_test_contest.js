import http from "k6/http";
import { check, sleep } from "k6";

export const options = {
  vus: 50,
  duration: "3m",
  thresholds: {
    http_req_failed: ["rate<0.01"],
    http_req_duration: ["p(95)<2000"],
  },
};

const BASE = __ENV.BASE_URL || "http://localhost:8000/api/v1";
const USERNAME = __ENV.USERNAME || "participant1";
const PASSWORD = __ENV.PASSWORD || "participant1@123";

function login() {
  const res = http.post(
    `${BASE}/auth/login`,
    JSON.stringify({ username: USERNAME, password: PASSWORD }),
    { headers: { "Content-Type": "application/json" } },
  );
  check(res, { "login ok": (r) => r.status === 200 });
  const body = res.json();
  return body?.access_token || "";
}

export default function () {
  const token = login();
  if (!token) {
    sleep(1);
    return;
  }

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const runRes = http.post(
    `${BASE}/submissions/test-run`,
    JSON.stringify({
      question_id: "question1",
      language: "python",
      code: "def find_isomorphic_strings(s, arr):\n    return arr\n",
    }),
    { headers },
  );
  check(runRes, { "test-run accepted": (r) => r.status === 200 });

  const submitRes = http.post(
    `${BASE}/submissions/submit`,
    JSON.stringify({
      question_id: "question1",
      language: "python",
      code: "def find_isomorphic_strings(s, arr):\n    return arr\n",
    }),
    { headers },
  );
  check(submitRes, { "submit queued": (r) => r.status === 201 });

  sleep(1);
}
