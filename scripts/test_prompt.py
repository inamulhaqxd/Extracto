import httpx
import json

prompt = """You are an expert technical document evaluator. Extract precise, concise answers from the reference document.

REFERENCE EXCERPTS:
--- [Page 1 | Summary] ---
Incident Report - INC-2091
Core Network / Datacenter Operations
On the night of 14 March, the NOC received automated alerts indicating packet loss on the core distribution switch serving Datacenter Hall B. Within minutes, downstream monitoring showed degraded performance on the billing database cluster and intermittent failures on the customer self-service portal. The issue was traced to a failed uplink transceiver on switch DC-B-CORE-02, which had gone unnoticed after a routine firmware update earlier that day introduced a change to spanning-tree priority values. This report was compiled by the on-call NOC lead as part of standard post-incident review.

--- [Page 1 | Timeline] ---
23:14 - First Grafana alert fires: elevated packet loss (>4%) on DC-B-CORE-02 uplink port. Duty engineer acknowledges within 2 minutes.
23:19 - Billing database cluster reports replication lag exceeding 30 seconds on two of three nodes.
23:26 - Customer self-service portal begins returning intermittent 502 errors; roughly 1 in 5 requests affected.
23:31 - On-call NOC lead escalates to network engineering; incident bridge opened.
23:48 - Root cause identified as a failed SFP+ transceiver on the uplink port, compounded by a spanning-tree priority change from the 09:00 firmware update that delayed automatic failover to the redundant path.
00:05 - Faulty transceiver physically replaced by on-site technician.
00:12 - Uplink port restored; packet loss returns to baseline.
00:21 - Billing database replication lag returns to normal (under 1 second).
00:27 - Customer portal error rate confirmed back to 0%; incident declared resolved.

--- [Page 1 | Affected Systems] ---
DC-B-CORE-02 (core switch) Uplink packet loss, degraded throughput
Billing database cluster Replication lag, delayed transaction posting
Customer self-service portal Intermittent HTTP 502 errors (~20% of requests)
Internal monitoring dashboard No impact - remained available throughout

--- [Page 2 | Root Cause Analysis] ---
The primary trigger was hardware failure of an SFP+ transceiver on the DC-B-CORE-02 uplink. Under normal conditions, this class of failure triggers automatic failover to the redundant uplink within seconds. However, the 09:00 firmware update that day had reset spanning-tree bridge priority on DC-B-CORE-02 to its default value, making it compete for root bridge status instead of yielding to the redundant path. This delayed convergence and extended the outage window well beyond what a simple transceiver failure should have caused. This is the second transceiver-related failure on the DC-B rack in the past six months; the first occurred in October on a different port and was resolved without cascading impact because the spanning-tree configuration was unaffected at that time.

--- [Page 2 | Resolution and Follow-up Actions] ---
Immediate resolution involved physical replacement of the failed transceiver. Follow-up actions assigned: (1) audit spanning-tree priority settings across all core switches to confirm they match documented standards, post firmware updates; (2) add a post-update configuration diff check to the firmware update runbook; (3) evaluate stocking additional spare transceivers at the DC-B site given this is the second failure in six months. Action items were assigned to the network engineering team with a two-week deadline.

TASK:
For each question, provide:
1. "answer": Concise, direct value (1-8 words max, e.g. "INC-2091", "73 minutes (1 hr 13 min)", "DC-B-CORE-02, Billing database cluster, Customer self-service portal", "3 action items"). If not specified in the document, answer "Not specified in report".
2. "source_section": The section name and page from the excerpts (e.g. "Timeline (Page 1)", "Resolution and Follow-up Actions (Page 2)").

QUESTIONS:
1. Incident ID
2. Root cause device/component
3. Time the incident started (first alert)
4. Time the incident was declared resolved
5. Total incident duration (calculate from start/end times)
6. List all systems affected (not including systems explicitly stated as unaffected)
7. Approximate error rate on the customer portal during the incident
8. Was this the first time this type of failure occurred on this rack? Explain.
9. How many follow-up action items were assigned?
10. Deadline given for follow-up actions
11. Name of the person who approved the final RCA report

Return valid JSON format:
{
  "answers": [
    {"question": "...", "answer": "...", "source_section": "..."}
  ]
}
"""

res = httpx.post("http://localhost:11434/api/chat", json={
    "model": "qwen2.5:1.5b",
    "messages": [{"role": "user", "content": prompt}],
    "format": "json",
    "stream": False,
    "options": {"temperature": 0.1, "num_ctx": 2048}
}, timeout=60.0)

print(json.dumps(res.json().get("message", {}).get("content"), indent=2))
