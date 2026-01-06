🛡️ ECOSHIELD AGENT v1.0
Automated Human-Risk Intelligence & SOAR Response Engine

📖 Overview

ECOSHIELD is a cybersecurity framework designed to bridge the gap between human error and automated defense. Developed as part of the EcoTechLabs simulation suite, it simulates department-specific phishing threats (Finance, Health, Tech) and utilizes an autonomous "Sentinel" to execute lockdown protocols when risk thresholds are exceeded.

🚀 Core Components
The Vault (vault.py): The central "Source of Truth." A secure SQLite database holding employee identities and real-time risk profiles.

The Trap (trap.py): The "Front Line." A dynamic Flask-based simulation engine that uses White-Label Branding to create realistic login tests.

The Sentinel (sentinel.py): The "Auto-Defender." A background monitoring script that executes Lockdown Protocols (SOAR) when a user reaches "Critical Risk."

Visual Dashboard (dashboard.py): The "Command Center." An ASCII-based analytics suite for rapid risk visualization across the organization.

🛠️ Installation & Usage
Initialize the Vault: python vault.py

Start the Sentinel: python sentinel.py

Launch the Simulation: python trap.py

View Analytics: python dashboard.py

🔐 Security Features
Dynamic Luring: URL parameters (e.g., ?dept=finance) trigger instant UI branding changes.

Autonomous Response: Real-time credential locking without human intervention.

Anti-Forensics (WIP): Integrated "Self-Destruct" logic to wipe sensitive data if unauthorized admin access is detected.

⚖️ License
Proprietary / All Rights Reserved. This project is part of my professional portfolio. Unauthorized copying, modification, or distribution of this code via any medium is strictly prohibited.

Developed by @eco4x | Powered by EcoTechLabs Security
