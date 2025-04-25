import subprocess
import time
import requests
import csv
import os
from packaging.version import parse as parse_version

# CONFIG
REPO_PATH = "/Users/francescoastolfi/progetto-java/bookeeper_def/bookkeeper"  # <-- cambia con il tuo path locale
SONAR_PROJECT_KEY = "bookkeeper"
SONAR_HOST = "http://localhost:9000"
SONAR_TOKEN = "squ_ad27e475ac9432d248697d6ffe4140ce44767f2e"
METRICS = "ncloc,complexity,duplicated_lines_density"
OUTPUT_CSV = "release_metrics.csv"
ERROR_LOG = "error_log.txt"


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Errore eseguendo: {cmd}")
        print(f"🔻 STDERR:\n{result.stderr}")
        print(f"🔻 STDOUT:\n{result.stdout}")
    return result.stdout.strip()


def analyze_with_sonar(tag):
    print(f"📦 Analisi di {tag} in corso...")

    # Salva eventuali modifiche locali
    run("git stash", cwd=REPO_PATH)

    # Checkout al tag specifico
    run(f"git checkout {tag}", cwd=REPO_PATH)

    # Compilazione del progetto senza test
    run("mvn clean compile -Dmaven.test.skip=true", cwd=REPO_PATH)

    # Esecuzione analisi Sonar
    sonar_cmd = (
        f"mvn verify sonar:sonar "
        f"-Dsonar.projectKey={SONAR_PROJECT_KEY} "
        f"-Dsonar.host.url={SONAR_HOST} "
        f"-Dsonar.login={SONAR_TOKEN} "
        f"-Dsonar.projectVersion={tag} "
        f"-Dmaven.test.skip=true"
    )
    run(sonar_cmd, cwd=REPO_PATH)

    print("⏳ In attesa che SonarQube completi l'analisi...")
    time.sleep(60)  # Attendi 60 secondi


def fetch_metrics(tag):
    url = f"{SONAR_HOST}/api/measures/component"
    params = {
        "component": SONAR_PROJECT_KEY,
        "metricKeys": METRICS
    }
    auth = (SONAR_TOKEN, "")
    response = requests.get(url, params=params, auth=auth)
    data = response.json()

    metrics = {m["metric"]: m["value"] for m in data["component"]["measures"]}
    metrics["version"] = tag
    return metrics


def main():
    # Recupera e filtra i tag del repository
    tags = run("git tag", cwd=REPO_PATH).splitlines()
    tags = [t for t in tags if t.startswith("release-") and "-docker" not in t]

    # Ordina dalla versione più vecchia alla più recente
    tags.sort(key=lambda t: parse_version(t.replace("release-", "")))
    print(f"🔍 Trovate {len(tags)} versioni da analizzare.")

    all_metrics = []

    for tag in tags:
        try:
            analyze_with_sonar(tag)
            metrics = fetch_metrics(tag)
            all_metrics.append(metrics)
        except Exception as e:
            print(f"❌ Errore nella versione {tag}: {e}")
            with open(ERROR_LOG, "a") as log:
                log.write(f"{tag}: {str(e)}\n")

    # Scrive su CSV
    fieldnames = ["version"] + METRICS.split(",")
    with open(OUTPUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_metrics:
            writer.writerow(row)

    print(f"✅ Dati salvati in {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
