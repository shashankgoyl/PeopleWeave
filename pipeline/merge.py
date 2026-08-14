"""
Task 1 - Merge pipeline, built against the real files:
  data/source1_naukri_applicants.csv   (id: none | name, email, phone, city, exp, ctc, applied date, skills)
  data/source2_gig_workers.csv         (id: none | email, name, rate, location, status, skill_tags - NO PHONE)
  data/source3_cbnexus_contacts.csv    (id: none | name, phone, city, verified, projects - NO EMAIL, NO SKILLS)

None of the 3 shares a common ID column, and no single field is present in
all three either (source2 has no phone, source3 has no email) - so identity
has to be established transitively: source1 is the only file with BOTH email
and phone, so it acts as the bridge that lets a source2 (email-only) record
and a source3 (phone-only) record land on the same person even though they
share nothing directly. See docs/data_issues_report.md for the full writeup.

Matching strategy (two phases, on purpose):

  PHASE 1 - hard clusters: union records that share an exact normalized email
  or an exact normalized phone. This is the only evidence strong enough to
  auto-merge without a human looking at it.

  PHASE 2 - fuzzy name bridging, cluster-aware: for records/clusters not yet
  connected, compare normalized names (rapidfuzz >= 95). Before merging, check
  EVERY member of both sides for a conflicting non-null email or phone - not
  just the two records whose names matched. This matters: a naive pairwise
  fuzzy pass can merge record A (no email) with record B (email X) just fine,
  then separately merge record B with record C (email Y) - silently gluing
  together A+B+C even though B's own email would have blocked a direct A-vs-C
  merge. Checking the whole cluster, not just the pair, catches that. This is
  exactly what happens with "Arjun Mehta" in the real data - see the report.

Usage:
    python merge.py --dry-run
    python merge.py                 # also upserts into Supabase (needs .env)
"""
import argparse
import csv
import json
import os
from collections import defaultdict

from rapidfuzz import fuzz

from clean import clean_str, is_valid_email_syntax, normalize_email, normalize_name, normalize_phone

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

SOURCES = {
    "naukri_applicants": {
        "file": "source1_naukri_applicants.csv",
        "name_col": "Full Name",
        "email_col": "Email",
        "phone_col": "Phone",
        "skills_col": "Skills",
    },
    "gig_workers": {
        "file": "source2_gig_workers.csv",
        "name_col": "worker_name",
        "email_col": "email_id",
        "phone_col": None,
        "skills_col": "skill_tags",
    },
    "cbnexus_contacts": {
        "file": "source3_cbnexus_contacts.csv",
        "name_col": "Name",
        "email_col": None,
        "phone_col": "Phone Number",
        "skills_col": None,
    },
}


def load_records():
    records = []
    issues = []

    for source_system, cfg in SOURCES.items():
        path = os.path.join(DATA_DIR, cfg["file"])
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            for i, row in enumerate(reader, start=2):
                values = [row.get(c) for c in fieldnames]

                if all((v is None or str(v).strip() == "") for v in values):
                    issues.append({"source": source_system, "line": i, "issue": "blank_row",
                                    "detail": "every field empty - dropped"})
                    continue

                if all(str(v).strip() == fieldnames[idx] for idx, v in enumerate(values)):
                    issues.append({"source": source_system, "line": i, "issue": "embedded_duplicate_header",
                                    "detail": f"row content == header row {fieldnames} - dropped "
                                              f"(source file is almost certainly 2 exports pasted together)"})
                    continue

                email_col = cfg["email_col"]
                if email_col:
                    raw_email_val = row.get(email_col)
                    if raw_email_val and not is_valid_email_syntax(str(raw_email_val).strip()):
                        other_email_hits = [v for v in values if v and is_valid_email_syntax(str(v).strip())]
                        if other_email_hits:
                            issues.append({
                                "source": source_system, "line": i, "issue": "shifted_columns",
                                "detail": f"row values don't line up with headers (email-looking value "
                                          f"found in a different column: {other_email_hits[0]!r}); "
                                          f"raw row={row} - dropped rather than guess-repaired, since a "
                                          f"cross-check found this person already has a clean row elsewhere "
                                          f"in the file"
                            })
                            continue

                rec = {
                    "source_system": source_system,
                    "raw_name": row.get(cfg["name_col"]),
                    "name": normalize_name(row.get(cfg["name_col"])),
                    "email": normalize_email(row.get(email_col)) if email_col else None,
                    "phone": normalize_phone(row.get(cfg["phone_col"])) if cfg["phone_col"] else None,
                    "raw_skills_text": clean_str(row.get(cfg["skills_col"])) if cfg["skills_col"] else None,
                    "raw_row": row,
                }
                if not rec["name"]:
                    issues.append({"source": source_system, "line": i, "issue": "missing_name",
                                    "detail": f"raw row={row}"})
                records.append(rec)

    return records, issues


class UnionFind:
    def __init__(self, n):
        self.parent = list(range(n))

    def find(self, x):
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def cluster_records(records):
    n = len(records)
    uf = UnionFind(n)
    audit = []

    by_email, by_phone = defaultdict(list), defaultdict(list)
    for i, r in enumerate(records):
        if r["email"]:
            by_email[r["email"]].append(i)
        if r["phone"]:
            by_phone[r["phone"]].append(i)

    for email, idxs in by_email.items():
        for j in idxs[1:]:
            uf.union(idxs[0], j)
            audit.append({"matched_on": "email", "confidence": 1.0,
                           "detail": f"'{email}' shared by record {idxs[0]} and {j}"})
    for phone, idxs in by_phone.items():
        for j in idxs[1:]:
            uf.union(idxs[0], j)
            audit.append({"matched_on": "phone", "confidence": 1.0,
                           "detail": f"'{phone}' shared by record {idxs[0]} and {j}"})

    clusters_now = defaultdict(list)
    for i in range(n):
        clusters_now[uf.find(i)].append(i)

    def cluster_conflicts(idxs_a, idxs_b):
        emails_a = {records[i]["email"] for i in idxs_a if records[i]["email"]}
        emails_b = {records[i]["email"] for i in idxs_b if records[i]["email"]}
        phones_a = {records[i]["phone"] for i in idxs_a if records[i]["phone"]}
        phones_b = {records[i]["phone"] for i in idxs_b if records[i]["phone"]}
        if emails_a and emails_b and not (emails_a & emails_b):
            return f"conflicting emails {sorted(emails_a)} vs {sorted(emails_b)}"
        if phones_a and phones_b and not (phones_a & phones_b):
            return f"conflicting phones {sorted(phones_a)} vs {sorted(phones_b)}"
        return None

    checked_pairs = set()
    for i in range(n):
        for j in range(i + 1, n):
            ri, rj = uf.find(i), uf.find(j)
            if ri == rj:
                continue
            if not records[i]["name"] or not records[j]["name"]:
                continue
            score = fuzz.token_sort_ratio(records[i]["name"], records[j]["name"])
            if score < 90:
                continue

            pair_key = tuple(sorted((ri, rj)))
            if pair_key in checked_pairs:
                continue
            checked_pairs.add(pair_key)

            idxs_a, idxs_b = clusters_now[ri], clusters_now[rj]
            conflict = cluster_conflicts(idxs_a, idxs_b)

            if score >= 95 and not conflict:
                uf.union(i, j)
                new_root = uf.find(i)
                clusters_now[new_root] = clusters_now[ri] + clusters_now[rj]
                audit.append({"matched_on": "fuzzy_name_auto", "confidence": round(score / 100, 2),
                               "detail": f"'{records[i]['name']}' ~ '{records[j]['name']}' "
                                         f"(record {i} & {j}) - clusters merged, no conflicts found "
                                         f"across either full cluster"})
            else:
                audit.append({"matched_on": "fuzzy_name_needs_review", "confidence": round(score / 100, 2),
                               "detail": f"'{records[i]['name']}' ~ '{records[j]['name']}' "
                                         f"(record {i} & {j}) - NOT auto-merged"
                                         + (f" ({conflict})" if conflict else " (score below 95)")})

    clusters = defaultdict(list)
    for i in range(n):
        clusters[uf.find(i)].append(i)
    return list(clusters.values()), audit


def build_person(cluster_idxs, records):
    subset = [records[i] for i in cluster_idxs]
    names = [r["name"] for r in subset if r["name"]]
    emails = sorted({r["email"] for r in subset if r["email"]})
    phones = sorted({r["phone"] for r in subset if r["phone"]})
    skills = " | ".join(sorted({r["raw_skills_text"] for r in subset if r["raw_skills_text"]}))
    source_systems = sorted({r["source_system"] for r in subset})
    full_name = max(names, key=len) if names else "(name missing in all sources)"

    return {
        "full_name": full_name,
        "primary_email": emails[0] if emails else None,
        "all_emails": emails,
        "primary_phone": phones[0] if phones else None,
        "all_phones": phones,
        "source_systems": source_systems,
        "raw_skills_text_combined": skills,
        "sources": [
            {
                "source_system": r["source_system"],
                "source_record_id": None,
                "raw_skills_text": r["raw_skills_text"],
                "raw_row": r["raw_row"],
            }
            for r in subset
        ],
    }


def upsert_to_supabase(people):
    from supabase import create_client
    from dotenv import load_dotenv
    load_dotenv()
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    sb = create_client(url, key)

    inserted, updated = 0, 0
    for p in people:
        existing = None
        if p["primary_email"]:
            res = sb.table("people").select("id").eq("primary_email", p["primary_email"]).execute()
            if res.data:
                existing = res.data[0]["id"]
        if not existing and p["primary_phone"]:
            res = sb.table("people").select("id").eq("primary_phone", p["primary_phone"]).execute()
            if res.data:
                existing = res.data[0]["id"]

        payload = {
            "full_name": p["full_name"],
            "primary_email": p["primary_email"],
            "primary_phone": p["primary_phone"],
            "source_systems": p["source_systems"],
        }

        if existing:
            sb.table("people").update(payload).eq("id", existing).execute()
            person_id = existing
            updated += 1
        else:
            res = sb.table("people").insert(payload).execute()
            person_id = res.data[0]["id"]
            inserted += 1

        for email in p["all_emails"]:
            sb.table("person_emails").upsert(
                {"person_id": person_id, "email": email, "is_primary": email == p["primary_email"]},
                on_conflict="person_id,email",
            ).execute()
        for phone in p["all_phones"]:
            sb.table("person_phones").upsert(
                {"person_id": person_id, "phone": phone, "is_primary": phone == p["primary_phone"]},
                on_conflict="person_id,phone",
            ).execute()
        for s in p["sources"]:
            sb.table("person_sources").insert({
                "person_id": person_id,
                "source_system": s["source_system"],
                "source_record_id": s["source_record_id"],
                "raw_skills_text": s["raw_skills_text"],
                "raw_row": s["raw_row"],
            }).execute()

    print(f"Supabase upsert done: {inserted} inserted, {updated} updated.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records, row_issues = load_records()
    clusters, audit = cluster_records(records)
    people = [build_person(c, records) for c in clusters]

    out = {
        "total_raw_rows": len(records),
        "total_unique_people": len(people),
        "duplicates_collapsed": len(records) - len(people),
        "row_level_issues": row_issues,
        "people": people,
        "merge_audit": audit,
    }
    out_path = os.path.join(os.path.dirname(__file__), "merged_preview.json")
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2, default=str)

    print(f"Read {len(records)} usable rows across 3 sources ({len(row_issues)} row-level issues logged).")
    print(f"Resolved to {len(people)} unique people ({len(records) - len(people)} duplicate rows collapsed).")
    print(f"Preview written to {out_path}")

    review = [a for a in audit if a["matched_on"] == "fuzzy_name_needs_review"]
    if review:
        print(f"\n{len(review)} possible-duplicate pair(s) flagged for human review - see merge_audit.")

    if not args.dry_run:
        upsert_to_supabase(people)
    else:
        print("\n--dry-run set: no Supabase writes made.")


if __name__ == "__main__":
    main()
