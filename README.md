# Daily Disable Accounts - Automation Script 

## Overview
This project is a production aimed Python automation that identifies inactive user accounts in Auth0 and safely disables them based on a defined inactivity policy. It is designed to provide real operational support engineering work, including:

* **Secure Authentication:** Integration with the Auth0 Management API.
* **Policy-Driven Management:** Account lifecycle automation.
* **Safe Execution:** Dry-run modes to prevent accidental data loss.
* **Compliance Ready:** Structured logging and audit reporting.

---

## Key Features

### Policy Based Inactivity Detection
* Scans users created after a configurable policy start date.
* Calculates account age in days and flags those exceeding the threshold.

### Safe Execution Modes
* **Dry Run (Default):** Reports accounts that *would* be disabled without making changes.
* **Live Mode:** Disables expired accounts and records detailed metadata.

### Intelligent Account Protection
To mirror real enterprise safety controls, the script automatically skips:
- [x] Already blocked accounts
- [x] Accounts created before the policy start date
- [x] Social or SSO connections/ Protected Connections (Google, Okta, etc.)

---

## Tech Stack
* **Language:** Python 3.x
* **API:** Auth0 Management API
* **Configuration:** `python-dotenv` for secure secret management
* **Reporting:** CSV & Structured Logging

---

## Environment Configuration
Create a `.env` file in the root directory. **Do not commit this file to GitHub.**


```bash
AUTH0_DOMAIN=your-domain.auth0.com
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret

MAXIMUM_DAYS=30
POLICY_START=2024-01-01T00:00:00
DRY_RUN=true

```


## Author
Charmaine Olupitan
* Technical Engineer and Developer .
