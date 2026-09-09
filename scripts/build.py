#!/usr/bin/env python3

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIR = ROOT / "source"
SRS_DIR = ROOT / "srs"
MRS_DIR = ROOT / "mrs"

SRS_DIR.mkdir(parents=True, exist_ok=True)
MRS_DIR.mkdir(parents=True, exist_ok=True)


def parse_rules(file_path):
    """
    读取 Mihomo/Clash 风格规则：

    DOMAIN,example.com
    DOMAIN-SUFFIX,example.com
    DOMAIN-KEYWORD,example
    IP-CIDR,1.2.3.0/24
    IP-CIDR6,2001:db8::/32
    """

    rules = {
        "domain": [],
        "domain_suffix": [],
        "domain_keyword": [],
        "ip_cidr": [],
    }

    with file_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()

            # 空行
            if not line:
                continue

            # 注释
            if line.startswith("#"):
                continue

            parts = [x.strip() for x in line.split(",", 2)]

            if len(parts) < 2:
                print(
                    f"WARNING: {file_path}:{line_no} "
                    f"无法识别，跳过: {line}"
                )
                continue

            rule_type = parts[0].upper()
            value = parts[1]

            if not value:
                continue

            if rule_type == "DOMAIN":
                rules["domain"].append(value)

            elif rule_type == "DOMAIN-SUFFIX":
                rules["domain_suffix"].append(value)

            elif rule_type == "DOMAIN-KEYWORD":
                rules["domain_keyword"].append(value)

            elif rule_type in ("IP-CIDR", "IP-CIDR6"):
                rules["ip_cidr"].append(value)

            else:
                print(
                    f"WARNING: {file_path}:{line_no} "
                    f"未知规则类型，跳过: {line}"
                )

    # 去重，同时保持原顺序
    for key in rules:
        rules[key] = list(dict.fromkeys(rules[key]))

    return rules


def build_srs(name, rules):
    """
    生成 sing-box SRS。
    """

    json_path = SRS_DIR / f"{name}.json"
    srs_path = SRS_DIR / f"{name}.srs"

    # sing-box rule-set source format
    rule_set = {
        "version": 2,
        "rules": []
    }

    if rules["domain"]:
        rule_set["rules"].append({
            "domain": rules["domain"]
        })

    if rules["domain_suffix"]:
        rule_set["rules"].append({
            "domain_suffix": rules["domain_suffix"]
        })

    if rules["domain_keyword"]:
        rule_set["rules"].append({
            "domain_keyword": rules["domain_keyword"]
        })

    if rules["ip_cidr"]:
        rule_set["rules"].append({
            "ip_cidr": rules["ip_cidr"]
        })

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(
            rule_set,
            f,
            ensure_ascii=False,
            indent=2
        )

    print(f"Building SRS: {srs_path}")

    subprocess.run(
        [
            "sing-box",
            "rule-set",
            "compile",
            str(json_path),
            "-o",
            str(srs_path),
        ],
        check=True,
    )

    json_path.unlink()

    print(f"OK: {srs_path}")


def build_mrs(name, rules):
    """
    生成 Mihomo MRS。

    domain 和 ipcidr 必须分别编译。
    如果一个规则文件同时包含两者，则生成两个 MRS：
      xxx-domain.mrs
      xxx-ipcidr.mrs

    对于你现在的 arr.list：
      全部是 DOMAIN / DOMAIN-SUFFIX
    因此只会生成：
      arr.mrs
    """

    has_domain = (
        rules["domain"]
        or rules["domain_suffix"]
        or rules["domain_keyword"]
    )

    has_ip = bool(rules["ip_cidr"])

    if has_domain:
        domain_source = MRS_DIR / f".{name}-domain.txt"
        domain_output = MRS_DIR / f"{name}.mrs"

        with domain_source.open("w", encoding="utf-8") as f:

            for domain in rules["domain"]:
                f.write(f"DOMAIN,{domain}\n")

            for domain in rules["domain_suffix"]:
                f.write(f"DOMAIN-SUFFIX,{domain}\n")

            for domain in rules["domain_keyword"]:
                f.write(f"DOMAIN-KEYWORD,{domain}\n")

        print(f"Building MRS: {domain_output}")

        subprocess.run(
            [
                "mihomo",
                "convert-ruleset",
                "domain",
                "text",
                str(domain_source),
                str(domain_output),
            ],
            check=True,
        )

        domain_source.unlink()

        print(f"OK: {domain_output}")

    if has_ip:
        ip_source = MRS_DIR / f".{name}-ipcidr.txt"
        ip_output = MRS_DIR / f"{name}-ipcidr.mrs"

        with ip_source.open("w", encoding="utf-8") as f:
            for cidr in rules["ip_cidr"]:
                f.write(f"{cidr}\n")

        print(f"Building MRS: {ip_output}")

        subprocess.run(
            [
                "mihomo",
                "convert-ruleset",
                "ipcidr",
                "text",
                str(ip_source),
                str(ip_output),
            ],
            check=True,
        )

        ip_source.unlink()

        print(f"OK: {ip_output}")


def build_file(file_path):
    name = file_path.stem

    print()
    print("=" * 60)
    print(f"Processing: {file_path}")
    print("=" * 60)

    rules = parse_rules(file_path)

    total = sum(len(v) for v in rules.values())

    print(f"DOMAIN        : {len(rules['domain'])}")
    print(f"DOMAIN-SUFFIX : {len(rules['domain_suffix'])}")
    print(f"DOMAIN-KEYWORD: {len(rules['domain_keyword'])}")
    print(f"IP-CIDR       : {len(rules['ip_cidr'])}")
    print(f"TOTAL         : {total}")

    if total == 0:
        print("WARNING: no valid rules, skip")
        return

    build_srs(name, rules)
    build_mrs(name, rules)


def main():
    files = sorted(SOURCE_DIR.glob("*.list"))

    if not files:
        print("No .list files found in source/")
        return

    for file_path in files:
        build_file(file_path)

    print()
    print("=" * 60)
    print("All rules built successfully.")
    print("=" * 60)


if __name__ == "__main__":
    main()
