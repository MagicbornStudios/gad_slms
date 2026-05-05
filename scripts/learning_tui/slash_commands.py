from typing import Tuple, List, Dict

class SlashCommandParser:
    def __init__(self, model_labels: Dict[str, str], model_aliases: Dict[str, str]):
        self._model_labels = model_labels
        self._model_aliases = model_aliases

    def parse_slash_line(self, value: str) -> Tuple[str, str]:
        raw = value.strip()
        if not raw.startswith("/"):
            return "", ""
        inner = raw[1:].lstrip()
        if not inner:
            return "", ""
        parts = inner.split(maxsplit=1)
        first = parts[0].lower()
        rest = parts[1].strip().lower() if len(parts) > 1 else ""
        return first, rest

    def levenshtein_distance(self, left: str, right: str) -> int:
        if left == right:
            return 0
        if left == "":
            return len(right)
        if right == "":
            return len(left)
        previous = list(range(len(right) + 1))
        for left_index, left_char in enumerate(left, start=1):
            current = [left_index]
            for right_index, right_char in enumerate(right, start=1):
                insert_cost = current[right_index - 1] + 1
                delete_cost = previous[right_index] + 1
                replace_cost = previous[right_index - 1] + (left_char != right_char)
                current.append(min(insert_cost, delete_cost, replace_cost))
            previous = current
        return previous[-1]

    def command_stem_matches(self, stem: str, command: str) -> bool:
        if not stem:
            return True
        return command.startswith(stem)

    def families_for_stem(self, stem: str) -> List[str]:
        if stem == "":
            return ["model", "lesson", "help"]
        fams: List[str] = []
        if self.command_stem_matches(stem, "model") or self.command_stem_matches(stem, "models"):
            fams.append("model")
        if self.command_stem_matches(stem, "lesson"):
            fams.append("lesson")
        if self.command_stem_matches(stem, "help"):
            fams.append("help")
        if fams:
            return fams
        candidates = ("model", "models", "lesson", "help")
        typo_allowance = 1 if len(stem) < 5 else 2
        for cand in candidates:
            if self.levenshtein_distance(stem, cand) <= typo_allowance:
                if cand == "models":
                    fams.append("model")
                elif cand not in fams:
                    fams.append(cand)
        return fams

    def canonical_action_from_stem(self, stem: str) -> str | None:
        fams = self.families_for_stem(stem)
        if not fams:
            return None
        if len(fams) == 1:
            return fams[0]
        if stem in {"", "m", "mo", "mod", "mode"}:
            return "model"
        if stem in {"l", "le", "les", "less", "lesso"}:
            return "lesson"
        if stem in {"h", "he", "hel"}:
            return "help"
        return fams[0]

    def normalize_search_text(self, value: str) -> str:
        return " ".join(value.lower().replace("-", " ").replace("_", " ").split())

    def ranked_model_keys(self, query: str) -> List[str]:
        if not query:
            return list(self._model_labels)
        normalized = self.normalize_search_text(query)
        scored: List[Tuple[int, str]] = []
        for key, label in self._model_labels.items():
            label_n = self.normalize_search_text(label)
            key_n = self.normalize_search_text(key.replace("_", " "))
            hay = f"{key_n} {label_n}"
            score = 0
            if normalized == key_n or normalized == label_n:
                score += 200
            if key_n.startswith(normalized) or label_n.startswith(normalized):
                score += 120
            if normalized in hay:
                score += 70
            for alias, resolved in self._model_aliases.items():
                if resolved != key:
                    continue
                alias_n = self.normalize_search_text(alias.replace("-", " "))
                if alias_n.startswith(normalized) or normalized in alias_n:
                    score += 90
                score += max(0, 40 - self.levenshtein_distance(normalized, alias_n))
            score += max(0, 55 - self.levenshtein_distance(normalized, key_n))
            score += max(0, 45 - self.levenshtein_distance(normalized, label_n))
            typo_allowance = 1 if len(normalized) < 6 else 2
            if score == 0 and len(normalized) >= 2:
                best = min(
                    self.levenshtein_distance(normalized, w)
                    for w in (key_n, label_n, *hay.split())
                    if w
                )
                if best <= typo_allowance:
                    score = 30 - best
            if score > 0:
                scored.append((score, key))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [key for _s, key in scored] or list(self._model_labels)
