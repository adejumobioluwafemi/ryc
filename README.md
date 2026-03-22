# ✝️ RYC 2026 — Planning Committee Dashboard

> **Redeemed Youth Convention 2026**  
> Redeemed Christian Church of God, Russia  
> 📍 Moscow · 🗓️ April 30 – May 3, 2026

A Streamlit analytics dashboard for the RYC 2026 planning committee, providing real-time registration insights, financial summaries, and attendance analytics — all pulled live from the registration Google Sheet.

---

## 🚀 Live App

🔗 **[https://rycdashboard.streamlit.app](https://rycdashboard.streamlit.app)**  

**Admin Password:** `RYC2026@Admin`

---

## 📊 Dashboard Features

| Section | What it shows |
|---|---|
| **KPI Cards** | Total registrations, gender split, RCCG vs non-RCCG, accommodation requests, revenue, extra donations |
| **Demographics** | Gender distribution, RCCG membership status, accommodation needs |
| **Geography** | Registrants by city of residence, gender split per city |
| **Church & Parish** | RCCG parishes vs non-RCCG churches (separate + combined), church share pie |
| **Gender × Church** | Cross-analysis of gender breakdown per church/parish |
| **Financial Overview** | Contribution choice distribution, revenue breakdown (reg fees vs donations), tier distribution, revenue by church, top individual donors |
| **Accommodation** | Accommodation needs by city and by church |
| **Full Table** | Complete sortable registration table with summary stats |

---

## 🗂️ Project Structure

```
ryc-dashboard/
├── ryc_dashboard.py          # Main Streamlit app
├── requirements.txt          # Python dependencies
├── README.md                 # This file
└── .github/
    └── workflows/
        └── keep_alive.yml    # GitHub Actions ping to prevent app sleep
```

---

## ⚙️ Local Setup

### 1. Clone the repo
```bash
git clone https://github.com/rycdashboard/ryc-dashboard.git
cd ryc-dashboard
```

### 2. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate        # Mac/Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the app
```bash
streamlit run ryc_dashboard.py
```

The app opens at **http://localhost:8501**

---

## ☁️ Deployment (Streamlit Community Cloud)

1. Push this repo to GitHub
2. Go to **[share.streamlit.io](https://share.streamlit.io)** → Sign in with GitHub
3. Click **New app** and select:
   - **Repository:** `ryc-dashboard`
   - **Branch:** `main`
   - **Main file:** `ryc_dashboard.py`
4. Click **Deploy**

---

## 🔄 Data Source

Registration data is pulled **live** from the RYC 2026 Google Sheet:

- The sheet must be shared as **"Anyone with the link – Viewer"**
- Data is **cached for 5 minutes** to avoid excessive API calls
- Click the **🔄 Refresh** button in the dashboard for an instant sync

### Google Sheet columns used

| Column | Description |
|---|---|
| First Name / Last Name | Registrant identity |
| Gender | Male / Female |
| City | Current city of residence |
| RCCG Russia Member? | `Yes` = RCCG parish member · `No` = non-RCCG attendee |
| Church name (if applicable) | Parish name (RCCG) or independent church name (non-RCCG) |
| Will you need accommodation? | Accommodation planning |
| Would you like to contribute financially towards RYC? | Contribution tier selection |
| Freewill Donation | Used when "Yes, other amount" is selected |

### Financial logic

| Item | Detail |
|---|---|
| Registration fee | ₽8,000 per person (fixed) |
| `No please` | No extra donation |
| `Yes – ₽500 / ₽1,000 / ₽1,500 / ₽2,000 / ₽5,000` | Exact extra donation amount |
| `Yes, other amount` | Extra amount read from **Freewill Donation** column |
| **Person Total** | `₽8,000 + Extra Donation` |

---

## 🔒 Security

- The dashboard is **password-protected** — no data is visible without login
- The admin password is set in `ryc_dashboard.py` under `ADMIN_PASSWORD`
- To change it, update this line and redeploy:
  ```python
  ADMIN_PASSWORD = "RYC2026@Admin"
  ```

---

## ⏰ Keep-Alive (GitHub Actions)

Streamlit Community Cloud apps sleep after ~5 minutes of inactivity. The included GitHub Actions workflow pings the app every 10 minutes to keep it awake.

**File:** `.github/workflows/keep_alive.yml`

```yaml
on:
  schedule:
    - cron: '*/10 * * * *'   # every 10 minutes
  workflow_dispatch:           # manual trigger from GitHub UI
```

To activate:
1. Ensure the workflow file is committed to your repo
2. Go to the **Actions** tab in GitHub — the workflow runs automatically on schedule
3. To test immediately: **Actions → Keep RYC Dashboard Alive → Run workflow**

> ⚠️ **Note:** GitHub disables scheduled workflows automatically if the repo has no commits for **60 days**. Make a small commit or trigger a manual run to re-enable.

---

## 📦 Dependencies

```
streamlit>=1.32.0
pandas>=2.0.0
plotly>=5.18.0
numpy>=1.24.0
requests>=2.31.0
```

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---|---|
| `❌ Could not load Google Sheet` | Share the sheet as "Anyone with the link – Viewer" |
| `HTTP 400 / 403` error | Open the export URL in an incognito browser to confirm public access |
| App is sleeping | Check that `.github/workflows/keep_alive.yml` is committed and Actions are enabled |
| Charts not loading | Click 🔄 Refresh — data may have failed to cache on first load |
| Password rejected | Default is `RYC2026@Admin` — check for extra spaces when typing |
| GitHub Actions disabled | Go to Actions tab → click **Enable** or make a new commit |

---

## 👥 Maintained by

**RYC 2026 Planning Committee**  
Redeemed Christian Church of God, Russia  
🌐 [rccgrussia.org](https://rccgrussia.org)

---

*Dashboard built with [Streamlit](https://streamlit.io) · Charts by [Plotly](https://plotly.com) · Data from Google Sheets*
