Optional: Interne CA-Zertifikate (`*.crt`, PEM) hier ablegen, wenn der Docker-Build hinter einem
TLS-inspizierenden Proxy läuft (z. B. Root- und Issuing-CA). Sie werden im Build in die
Trust-Stores von Node (npm) und Python/Debian (pip/apt) übernommen.
