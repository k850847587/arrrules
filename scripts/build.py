import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source"
SRS = ROOT / "srs"
MRS = ROOT / "mrs"

SRS.mkdir(exist_ok=True)
MRS.mkdir(exist_ok=True)


def parse_list(path):
    rules = {
        "domain": [],
        "domain_suffix": [],
        "domain_keyword": [],
        "ip_cidr": [],
    }

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            parts = [x.strip() for x in line.split(",")]

            if len(parts) < 2:
                continue

            rule_type = parts[0].upper()
            value = parts[1]

            if rule_type == "DOMAIN":
                rules["domain"].append(value)

            elif rule_type == "DOMAIN-SUFFIX":
                rules["domain_suffix"].append(value)

            elif rule_type == "DOMAIN-KEYWORD":
                rules["domain_keyword"].append(value)

            elif rule_type in ("IP-CIDR", "IP-CIDR6"):
                rules["ip_cidr"].append(value)

    return {k: v for k, v in rules.items() if v}


def build_srs(name, rules):
    source = {
        "version": 2,
        "rules": [rules]
    }

    json_path = SRS / f"{name}.json"
    srs_path = SRS / f"{name}.srs"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(source, f, ensure_ascii=False, indent=2)

    subprocess.run(
        [
            "sing-box",
            "rule-set",
            "compile",
            str(json_path),
            "--output",
            str(srs_path),
        ],
        check=True,
    )

    json_path.unlink()


def build_mrs(name, source_path):
    mrs_path = MRS / f"{name}.mrs"

    subprocess.run(
        [
            "mihomo",
            "convert-ruleset",
            "domain",
            "text",
            str(source_path),
            str(mrs_path),
        ],
        check=True,
    )


def main():
    for source_path in SOURCE.glob("*.list"):
        name = source_path.stem

        print(f"Building {name}...")

        rules = parse_list(source_path)

        if not rules:
            print(f"Skip empty rule: {name}")
            continue

        build_srs(name, rules)

        # MRS 只适合纯 domain 规则
        # 如果包含 IP-CIDR，后面可以单独处理
        build_mrs(name, source_path)

        print(f"Done: {name}")


if __name__ == "__main__":
    main()
