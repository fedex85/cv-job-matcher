"""Genera data/skills/skills_db.json a partir de la lista semilla de este archivo.

Uso:  python scripts/build_skills_db.py

Para añadir una habilidad, edita SEED y vuelve a ejecutar el script.
Campos: (nombre canónico, categoría, familia o None, [alias]).
Las habilidades de la misma *familia* dan crédito parcial en el matching
(p. ej. pedir AWS y tener Azure). Los alias se comparan sin acentos ni mayúsculas.
"""

from __future__ import annotations

import json
from pathlib import Path

# Nombres que se buscan respetando mayúsculas (son palabras comunes en minúscula).
CASE_SENSITIVE = {"REST", "Swift", "Flux", "Chef", "Vault", "Spark"}

OUT = Path(__file__).resolve().parents[1] / "data" / "skills" / "skills_db.json"

SEED: list[tuple[str, str, str | None, list[str]]] = [
    # --- Lenguajes ---
    ("Python", "language", None, ["python3"]),
    ("Java", "language", None, []),
    ("JavaScript", "language", None, ["ecmascript"]),
    ("TypeScript", "language", None, []),
    ("Golang", "language", None, ["go lang"]),
    ("Rust", "language", None, []),
    ("C#", "language", None, ["csharp", "c sharp"]),
    ("C++", "language", None, ["cpp"]),
    ("PHP", "language", None, []),
    ("Ruby", "language", None, []),
    ("Kotlin", "language", None, []),
    ("Swift", "language", None, []),
    ("Scala", "language", None, []),
    ("Bash", "language", None, ["shell scripting", "shell script", "scripting en bash"]),
    ("PowerShell", "language", None, []),
    ("SQL", "language", None, []),
    ("Groovy", "language", None, []),
    # --- Cloud ---
    ("AWS", "cloud", "cloud-provider", ["amazon web services", "ec2", "s3", "amazon aws"]),
    ("Azure", "cloud", "cloud-provider", ["microsoft azure"]),
    ("Google Cloud", "cloud", "cloud-provider", ["gcp", "google cloud platform"]),
    ("Oracle Cloud", "cloud", "cloud-provider", ["oci"]),
    ("DigitalOcean", "cloud", "cloud-provider", []),
    ("AWS Lambda", "cloud", "serverless", ["lambda"]),
    ("Azure Functions", "cloud", "serverless", []),
    ("CloudFormation", "iac", "iac", ["aws cloudformation"]),
    ("EKS", "cloud", "container-orchestration", ["amazon eks"]),
    ("AKS", "cloud", "container-orchestration", ["azure kubernetes service"]),
    ("GKE", "cloud", "container-orchestration", []),
    ("VMware", "virtualization", "virtualization", ["vsphere", "esxi", "vcenter"]),
    ("Hyper-V", "virtualization", "virtualization", ["hyperv"]),
    ("Proxmox", "virtualization", "virtualization", []),
    ("OpenStack", "cloud", None, []),
    # --- Contenedores / orquestación ---
    ("Docker", "containers", "containers", ["contenedores docker", "dockerfile", "docker compose"]),
    ("Podman", "containers", "containers", []),
    ("Kubernetes", "containers", "container-orchestration", ["k8s"]),
    ("OpenShift", "containers", "container-orchestration", []),
    ("Helm", "containers", None, ["helm charts"]),
    ("Docker Swarm", "containers", "container-orchestration", []),
    ("ArgoCD", "cicd", "gitops", ["argo cd"]),
    ("Flux", "cicd", "gitops", ["fluxcd"]),
    # --- IaC / configuración ---
    ("Terraform", "iac", "iac", ["hcl"]),
    ("OpenTofu", "iac", "iac", []),
    ("Pulumi", "iac", "iac", []),
    ("Ansible", "iac", "config-mgmt", []),
    ("Puppet", "iac", "config-mgmt", []),
    ("Chef", "iac", "config-mgmt", []),
    ("SaltStack", "iac", "config-mgmt", ["salt stack"]),
    ("Packer", "iac", None, []),
    ("Vagrant", "iac", None, []),
    ("Infraestructura como código", "practice", None, ["infrastructure as code", "iac"]),
    # --- CI/CD ---
    ("Jenkins", "cicd", "ci-cd", []),
    ("GitHub Actions", "cicd", "ci-cd", []),
    ("GitLab CI", "cicd", "ci-cd", ["gitlab ci/cd", "gitlab-ci", "gitlab pipelines"]),
    ("Azure DevOps", "cicd", "ci-cd", ["azure pipelines", "ado"]),
    ("CircleCI", "cicd", "ci-cd", []),
    ("TeamCity", "cicd", "ci-cd", []),
    ("Bitbucket Pipelines", "cicd", "ci-cd", []),
    ("CI/CD", "practice", None, ["cicd", "integracion continua", "continuous integration",
                                  "despliegue continuo", "continuous delivery",
                                  "continuous deployment"]),
    ("GitOps", "practice", None, []),
    ("DevOps", "practice", None, []),
    ("SRE", "practice", None, ["site reliability engineering", "site reliability"]),
    ("DevSecOps", "practice", None, []),
    # --- Control de versiones ---
    ("Git", "tools", None, []),
    ("GitHub", "tools", "git-hosting", []),
    ("GitLab", "tools", "git-hosting", []),
    ("Bitbucket", "tools", "git-hosting", []),
    # --- Monitorización / observabilidad ---
    ("Prometheus", "observability", "monitoring", []),
    ("Grafana", "observability", "monitoring", []),
    ("Datadog", "observability", "monitoring", []),
    ("New Relic", "observability", "monitoring", []),
    ("Zabbix", "observability", "monitoring", []),
    ("Nagios", "observability", "monitoring", []),
    ("PRTG", "observability", "monitoring", []),
    ("ELK", "observability", "logging", ["elastic stack", "elasticsearch", "logstash", "kibana"]),
    ("Loki", "observability", "logging", ["grafana loki"]),
    ("Splunk", "observability", "logging", []),
    ("OpenTelemetry", "observability", None, ["otel"]),
    ("CloudWatch", "observability", "monitoring", ["aws cloudwatch"]),
    ("Observabilidad", "practice", None, ["observability"]),
    # --- Sistemas operativos / redes ---
    ("Linux", "systems", "os", ["gnu/linux", "ubuntu", "debian", "centos", "red hat", "rhel",
                                "rocky linux", "almalinux"]),
    ("Windows Server", "systems", "os", ["windows server 2016", "windows server 2019",
                                          "windows server 2022"]),
    ("Active Directory", "systems", None, ["directorio activo"]),
    ("Networking", "networking", None, ["redes de comunicaciones", "administracion de redes"]),
    ("TCP/IP", "networking", None, ["tcpip"]),
    ("DNS", "networking", None, []),
    ("DHCP", "networking", None, []),
    ("VPN", "networking", None, ["ipsec", "openvpn", "wireguard"]),
    ("BGP", "networking", None, []),
    ("OSPF", "networking", None, []),
    ("VLAN", "networking", None, ["vlans"]),
    ("Firewalls", "networking", None, ["firewall", "cortafuegos", "fortigate", "palo alto",
                                       "pfsense"]),
    ("Cisco", "networking", "network-vendor", ["ccna", "ccnp", "cisco ios"]),
    ("Load Balancing", "networking", None, ["balanceo de carga", "load balancer", "haproxy"]),
    ("Nginx", "networking", "web-server", []),
    ("Apache", "networking", "web-server", ["apache httpd"]),
    # --- Seguridad ---
    ("Ciberseguridad", "security", None, ["cybersecurity", "seguridad informatica", "information security", "seguridad de la informacion"]),
    ("IAM", "security", None, ["identity and access management"]),
    ("Vault", "security", None, ["hashicorp vault"]),
    ("SSL/TLS", "security", None, ["tls", "ssl", "certificados ssl"]),
    ("Trivy", "security", "sast-dast", []),
    ("SonarQube", "security", "sast-dast", []),
    ("OWASP", "security", None, []),
    ("Zero Trust", "security", None, []),
    # --- Bases de datos ---
    ("PostgreSQL", "database", "relational-db", ["postgres"]),
    ("MySQL", "database", "relational-db", ["mariadb"]),
    ("SQL Server", "database", "relational-db", ["mssql", "microsoft sql server"]),
    ("Oracle Database", "database", "relational-db", ["oracle db", "plsql", "pl/sql"]),
    ("MongoDB", "database", "nosql-db", []),
    ("Redis", "database", "nosql-db", []),
    ("Cassandra", "database", "nosql-db", []),
    ("DynamoDB", "database", "nosql-db", []),
    ("Elasticsearch", "database", None, []),
    # --- Mensajería / datos ---
    ("Kafka", "data", "messaging", ["apache kafka"]),
    ("RabbitMQ", "data", "messaging", []),
    ("Spark", "data", None, ["apache spark", "pyspark"]),
    ("Airflow", "data", None, ["apache airflow"]),
    ("Pandas", "data", None, []),
    ("Power BI", "data", "bi", ["powerbi"]),
    ("Tableau", "data", "bi", []),
    # --- Backend / frameworks ---
    ("FastAPI", "framework", "py-web", []),
    ("Django", "framework", "py-web", []),
    ("Flask", "framework", "py-web", []),
    ("Spring Boot", "framework", None, ["spring", "springboot"]),
    ("Node.js", "framework", None, ["nodejs", "node js"]),
    ("Express.js", "framework", None, ["expressjs", "express js"]),
    (".NET", "framework", None, ["dotnet", "asp.net", ".net core"]),
    ("Laravel", "framework", None, []),
    ("React", "framework", "js-frontend", ["reactjs", "react.js"]),
    ("Angular", "framework", "js-frontend", ["angularjs"]),
    ("Vue", "framework", "js-frontend", ["vue.js", "vuejs"]),
    ("HTML", "frontend", None, ["html5"]),
    ("CSS", "frontend", None, ["css3", "sass", "scss"]),
    ("REST", "practice", None, ["rest api", "restful", "apis rest", "api rest"]),
    ("GraphQL", "practice", None, []),
    ("Microservicios", "practice", None, ["microservices", "microservicio"]),
    # --- IA / ML ---
    ("Machine Learning", "ai", None, ["aprendizaje automatico"]),
    ("NLP", "ai", None, ["procesamiento del lenguaje natural", "natural language processing"]),
    ("PyTorch", "ai", "dl-framework", []),
    ("TensorFlow", "ai", "dl-framework", []),
    ("scikit-learn", "ai", None, ["sklearn"]),
    ("LLM", "ai", None, ["llms", "large language models", "modelos de lenguaje"]),
    ("MLOps", "ai", None, []),
    # --- Metodologías / otros ---
    ("Agile", "methodology", None, ["agil", "metodologias agiles", "agile methodologies"]),
    ("Scrum", "methodology", None, []),
    ("Kanban", "methodology", None, []),
    ("ITIL", "methodology", None, []),
    ("Jira", "tools", "pm-tools", []),
    ("Confluence", "tools", "pm-tools", []),
    ("Testing", "practice", None, ["pruebas automatizadas", "test automation", "unit testing",
                                    "tests unitarios", "pytest"]),
    ("Selenium", "tools", "test-tools", []),
    ("Cypress", "tools", "test-tools", []),
    ("Backup", "systems", None, ["backups", "copias de seguridad", "veeam", "disaster recovery",
                                  "recuperacion ante desastres"]),
    ("Alta disponibilidad", "practice", None, ["high availability"]),
    ("Automatización", "practice", None, ["automation", "automatizacion"]),
    ("Service Mesh", "containers", None, ["istio", "linkerd"]),
    ("Microsoft 365", "systems", None, ["office 365", "m365", "o365", "exchange online"]),
    ("Serverless", "cloud", None, []),
]


def build() -> dict:
    skills, seen = [], set()
    for name, category, family, aliases in SEED:
        if name.lower() in seen:
            raise ValueError(f"Habilidad duplicada en SEED: {name}")
        seen.add(name.lower())
        entry = {"name": name, "category": category, "aliases": sorted(set(aliases))}
        if family:
            entry["family"] = family
        if name in CASE_SENSITIVE:
            entry["case_sensitive"] = True
        skills.append(entry)
    return {"version": 1, "skills": skills}


if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(data['skills'])} habilidades escritas en {OUT}")
