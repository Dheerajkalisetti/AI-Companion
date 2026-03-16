# OmniCompanion — Security Model

## 1. Threat Model

### Attack Surface

| Surface | Threats | Severity |
|---------|---------|----------|
| User Input | Prompt injection, command injection | HIGH |
| Screen Data | Sensitive data exposure (passwords, PII) | HIGH |
| Gemini API | Prompt leakage, model manipulation | MEDIUM |
| gRPC Channel | Man-in-middle, unauthorized calls | MEDIUM |
| Firestore | Data tampering, unauthorized access | MEDIUM |
| OS Actions | Destructive commands, privilege escalation | CRITICAL |
| Browser | XSS via DOM manipulation, credential theft | HIGH |

### Threat Actors
1. **Malicious prompt** — User crafts input to make agent execute harmful actions
2. **Data exfiltration** — Agent inadvertently captures and transmits sensitive screen data
3. **Credential exposure** — API keys or tokens leaked in logs or code
4. **Destructive actions** — Agent deletes files, modifies system settings without consent

---

## 2. Security Controls

### 2.1 Input Sanitization
- All user inputs stripped of control characters
- Input length capped at 10,000 characters
- Shell metacharacters escaped before any system call
- Gemini prompts use structured delimiters to prevent injection

### 2.2 Action Classification (Safety Monitor Agent)

```
RISK LEVELS:
  LOW      → Read-only operations, screenshots, window listing
  MEDIUM   → Browser navigation, typing text, clicking UI elements
  HIGH     → File operations (create/rename/move), app install, settings change
  CRITICAL → File deletion, system pref changes, credential access, admin operations
```

**Enforcement:**
- LOW/MEDIUM → Auto-approved
- HIGH → Logged + proceed with warning in UI
- CRITICAL → **BLOCKED** — requires explicit user confirmation via UI dialog

### 2.3 Hardcoded Safety Rules (`config/safety_rules.yaml`)

```yaml
blocked_actions:
  - pattern: "rm -rf"
    risk: critical
    reason: "Recursive deletion is never allowed"
  - pattern: "sudo"
    risk: critical
    reason: "Privilege escalation not permitted"
  - pattern: "chmod 777"
    risk: critical
    reason: "Unsafe permission change"
  - pattern: "format"
    risk: critical
    reason: "Disk formatting not permitted"

blocked_paths:
  - "/System/*"
  - "/etc/*"
  - "~/.ssh/*"
  - "~/.gnupg/*"
  - "**/id_rsa*"
  - "**/password*"

blocked_domains:
  - "*.onion"
  - pattern: "file://"
    reason: "Local file access via browser blocked"
```

### 2.4 Credential Management
- **No hardcoded credentials** in any source file
- All secrets via environment variables (`.env` files, gitignored)
- GCP authentication via service account key file or application default credentials
- `.env.example` documents all required variables (without values)

### 2.5 Data Protection
- Screenshots stored in memory only during active processing
- Long-term screenshot storage in GCS with lifecycle policy (auto-delete after 30 days)
- PII detection prompt: Gemini checks screenshots for visible passwords/credentials before storage
- Firestore data encrypted at rest (GCP default)

### 2.6 Network Security
- gRPC communication on localhost only (127.0.0.1)
- No external gRPC endpoints exposed
- Vertex AI calls authenticated via service account
- Cloud Run requires authentication for all endpoints

### 2.7 Audit Logging
Every agent action logged to Cloud Logging:
```json
{
  "timestamp": "2026-03-05T02:30:00Z",
  "severity": "INFO",
  "agent": "action_executor",
  "action": "mouse_click",
  "target": {"x": 500, "y": 300},
  "risk_level": "low",
  "safety_approved": true,
  "duration_ms": 45,
  "success": true,
  "session_id": "uuid"
}
```

---

## 3. Mitigations Summary

| Threat | Mitigation | Status |
|--------|-----------|--------|
| Prompt injection | Structured delimiters + input sanitization | Phase 9 |
| Destructive OS actions | Safety Monitor + risk classification | Phase 3 (agent), Phase 9 (hardening) |
| Credential exposure | Env vars only, .gitignore enforcement | Phase 0 |
| Sensitive screen data | PII detection + short retention | Phase 9 |
| Unauthorized gRPC | Localhost binding only | Phase 5 |
| API abuse | Rate limiting on Gemini calls | Phase 9 |
| Data tampering | Firestore security rules + IAM | Phase 2 |
