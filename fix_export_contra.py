from pathlib import Path

p = Path("export_demo_fixtures.py")
src = p.read_text(encoding="utf-8")

old = '''        contra_tuple = find_contradictions(
            patient_id=patient_id,
            entities=all_entities,
            documents=documents,
        )
    except Exception as e:'''

new = '''        contra_tuple = find_contradictions(
            patient_id=patient_id,
            entities=all_entities,
            documents=documents,
        )
        # find_contradictions returns (rule_list, llm_list)
        contradictions = [
            c for sub in contra_tuple
            for c in (sub if isinstance(sub, list) else [sub])
            if isinstance(c, dict)
        ]
    except Exception as e:'''

if old not in src:
    print("[FAIL] anchor not found")
    raise SystemExit(1)
src = src.replace(old, new, 1)
p.write_text(src, encoding="utf-8")
print("[OK] contradiction unpacking added")