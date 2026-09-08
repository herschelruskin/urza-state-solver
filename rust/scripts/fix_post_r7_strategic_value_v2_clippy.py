from pathlib import Path

path = Path("rust/crates/urza-policy/src/lib.rs")
text = path.read_text()
old_head = '''        if matches!(information.phase, Phase::PrecombatMain) {
            if self.is_redundant_library_look(information, candidate) {
                return 7;
            }
            return match candidate.class {
'''
new_head = '''        if matches!(information.phase, Phase::PrecombatMain) {
            if self.is_redundant_library_look(information, candidate) {
                return 7;
            }
            match candidate.class {
'''
if text.count(old_head) != 1:
    raise SystemExit(f"expected one v2 main-phase return-match block, found {text.count(old_head)}")
text = text.replace(old_head, new_head, 1)
old_tail = '''                PolicyActionClass::PassPriority => 5,
                PolicyActionClass::ContingentDecision => 6,
            };
        } else {
'''
new_tail = '''                PolicyActionClass::PassPriority => 5,
                PolicyActionClass::ContingentDecision => 6,
            }
        } else {
'''
if text.count(old_tail) != 1:
    raise SystemExit(f"expected one v2 main-phase match tail, found {text.count(old_tail)}")
path.write_text(text.replace(old_tail, new_tail, 1))
