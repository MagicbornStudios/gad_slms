from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, RichLog

from . import icons
from .app_banner import AppBanner
from .lesson_screen import LessonScreen
from .lessons import LESSONS
from .models import Lesson, VisualContextTarget
from .vcs_tag import VcsTag
from .visual_context import VisualContextMixin

MAX_LESSON_SUGGESTIONS = 5


class MenuScreen(VisualContextMixin, Screen):
    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("enter", "open_highlighted", "Open"),
        Binding("alt+i", "toggle_visual_context", "VCS"),
    ]

    vcs_route = "/"
    vcs_targets = (
        VisualContextTarget("menu-shell", "Menu Shell", "pattern anchor: Small Language Model Lessons", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-details", "Main Chat Interface", "pattern anchor: Dr. Stein chat shell", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-chat", "Menu Chat Transcript", "pattern anchor: scripted chat/typewriter transcript", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("menu-composer", "Slash Command Composer", "pattern anchor: slash command lesson input", "scripts/learning_tui/menu_screen.py"),
        VisualContextTarget("lesson-suggestions", "Lesson Slash Suggestions", "pattern anchor: slash command lesson search results", "scripts/learning_tui/menu_screen.py"),
    )

    def __init__(self) -> None:
        super().__init__()
        self._typewriter_text = (
            "I build the small mind in public. Use /lesson tokenizer, /lesson 1, or /help to steer the lab."
        )
        self._typewriter_index = 0
        self._typewriter_timer = None
        self._conversation_panels = []
        self._visible_suggestion_indexes: list[int] = []
        self._setup_visual_context()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Button(f"{icons.DELETE}", id="app-exit", classes="header-exit")
        yield AppBanner(self.vcs_route, "SLM Learning")
        yield VcsTag("menu-shell", self.vcs_route)
        with Horizontal(id="menu-main"):
            with Vertical(id="menu-details"):
                yield VcsTag("menu-details", self.vcs_route)
                yield VcsTag("menu-chat", self.vcs_route)
                yield RichLog(id="menu-chat", highlight=True, markup=True, wrap=True)
                yield VcsTag("menu-composer", self.vcs_route)
                yield Input(
                    placeholder="/ to search lessons, /help",
                    id="menu-composer",
                )
                yield VcsTag("lesson-suggestions", self.vcs_route)
                yield ListView(
                    *[
                        ListItem(
                            Label("Type / to search lessons."),
                            id="lesson-suggestion-placeholder",
                            classes="suggestion-placeholder",
                        ),
                    ]
                    + [
                        ListItem(
                            Label(""),
                            id=f"lesson-suggestion-{index}",
                        )
                        for index in range(MAX_LESSON_SUGGESTIONS)
                    ],
                    id="lesson-suggestions",
                )
        yield Footer(id="textual-footer")

    def on_mount(self) -> None:
        self._seed_menu_chat()
        self._typewriter_timer = self.set_interval(0.035, self._tick_typewriter)
        self._sync_lesson_suggestions("")
        self._sync_visual_context()

    def _seed_menu_chat(self) -> None:
        self._render_menu_chat()

    def _render_menu_chat(self) -> None:
        chat = self.query_one("#menu-chat", RichLog)
        chat.clear()
        chat.write(
            Panel(
                Text(self._typewriter_text[: self._typewriter_index], style="#b4f9f8"),
                title=f"{icons.CHAT} Dr. Stein",
                border_style="cyan",
            )
        )
        for panel in self._conversation_panels:
            chat.write(panel)

    def _tick_typewriter(self) -> None:
        if self._typewriter_index >= len(self._typewriter_text):
            if self._typewriter_timer is not None:
                self._typewriter_timer.pause()
            return
        self._typewriter_index += 1
        self._render_menu_chat()

    def action_open_highlighted(self) -> None:
        suggestions = self.query_one("#lesson-suggestions", ListView)
        if suggestions.display and suggestions.index is not None:
            self._open_suggestion_item(suggestions.highlighted_child)

    def action_toggle_visual_context(self) -> None:
        self._toggle_visual_context()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        if event.list_view.id == "lesson-suggestions":
            self._open_suggestion_item(event.item)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "menu-composer":
            return
        event.stop()
        command = event.value.strip()
        event.input.value = ""
        self._handle_composer_command(command)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "menu-composer":
            return
        event.stop()
        self._sync_lesson_suggestions(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if self._handle_vcs_button(event.button.id):
            return
        if event.button.id == "app-exit":
            self.app.exit()

    def _sync_lesson_suggestions(self, value: str) -> None:
        suggestions = self.query_one("#lesson-suggestions", ListView)
        query = self._lesson_query_from_command(value)
        placeholder = self.query_one("#lesson-suggestion-placeholder", ListItem)
        self._visible_suggestion_indexes = []
        if query is None:
            placeholder.display = True
            for item in suggestions.children:
                if item.id != "lesson-suggestion-placeholder":
                    item.display = False
            return
        matches = self._matching_lessons(query)
        placeholder.display = len(matches) == 0
        self._visible_suggestion_indexes = [index for index, _lesson in matches[:MAX_LESSON_SUGGESTIONS]]
        for item in suggestions.children:
            if item.id == "lesson-suggestion-placeholder":
                continue
            try:
                slot = int(item.id.rsplit("-", 1)[1]) if item.id is not None else -1
            except (IndexError, ValueError):
                slot = -1
            if 0 <= slot < len(matches[:MAX_LESSON_SUGGESTIONS]):
                lesson_index, lesson = matches[slot]
                label = item.query_one(Label)
                label.update(self._format_lesson_suggestion(lesson_index, lesson, query))
                item.display = True
            else:
                item.display = False

    def _handle_composer_command(self, command: str) -> None:
        if command == "":
            return
        self._conversation_panels.append(Panel(Text(command, style="bright_white"), title="You", border_style="magenta"))
        if command in {"/help", "help"}:
            self._conversation_panels.append(
                Panel(
                    Text("/ or /les to search lessons | /lesson tokenizer | /lesson train-smoke | /help", style="bright_white"),
                    title=f"{icons.CHAT} Dr. Stein",
                    border_style="cyan",
                )
            )
            self._render_menu_chat()
            return
        if command.startswith("/lesson "):
            lesson = self._lesson_from_token(command.removeprefix("/lesson ").strip())
            if lesson is not None:
                self._conversation_panels.append(
                    Panel(
                        Text(f"Opening {lesson.title}.", style="bright_white"),
                        title=f"{icons.CHAT} Dr. Stein",
                        border_style="cyan",
                    )
                )
                self._render_menu_chat()
                self.app.push_screen(LessonScreen(lesson))
                return
        self._conversation_panels.append(
            Panel(
                Text("Unknown command. Try /help or /lesson tokenizer.", style="bright_white"),
                title=f"{icons.CHAT} Dr. Stein",
                border_style="yellow",
            )
        )
        self._render_menu_chat()

    def _lesson_query_from_command(self, value: str) -> str | None:
        command = value.strip().lower()
        if command == "/":
            return ""
        if command.startswith("/lesson"):
            return command.removeprefix("/lesson").strip()
        if command.startswith("/"):
            command_word, _, rest = command[1:].partition(" ")
            if "lesson".startswith(command_word):
                return rest.strip()
        return None

    def _matching_lessons(self, query: str) -> list[tuple[int, Lesson]]:
        if query == "":
            return list(enumerate(LESSONS))
        normalized = self._normalize_search_text(query)
        matches: list[tuple[int, int, Lesson]] = []
        for index, lesson in enumerate(LESSONS):
            score = self._score_lesson_match(normalized, index, lesson)
            if score > 0:
                matches.append((score, index, lesson))
        matches.sort(key=lambda match: (-match[0], match[1]))
        return [(index, lesson) for _score, index, lesson in matches]

    def _score_lesson_match(self, query: str, index: int, lesson: Lesson) -> int:
        lesson_number = str(index + 1)
        fields = [
            lesson_number,
            lesson.id,
            lesson.title,
            lesson.goal,
        ]
        normalized_fields = [self._normalize_search_text(field) for field in fields]
        haystack = " ".join(normalized_fields)
        words = set(haystack.split())
        query_words = set(query.split())

        score = 0
        if query == lesson_number or query == lesson.id:
            score += 160
        if lesson.id.startswith(query):
            score += 120
        if query in haystack:
            score += 80
        score += 18 * len(query_words & words)

        best_distance = min(
            self._levenshtein_distance(query, candidate)
            for candidate in [lesson.id, lesson_number, *words]
            if candidate
        )
        typo_allowance = 1 if len(query) < 6 else 2
        if best_distance <= typo_allowance:
            score += 70 - (best_distance * 20)

        if score == 0 and len(query) >= 3:
            # Keep plausible typo matches without flooding short, ambiguous input.
            closest_word = min((self._levenshtein_distance(query, word) for word in words), default=99)
            if closest_word <= max(2, len(query) // 3):
                score = 25 - closest_word
        return score

    def _format_lesson_suggestion(self, index: int, lesson: Lesson, query: str) -> str:
        prefix = "recommended" if query else "lesson"
        return f"{index + 1}. {icons.CHAT} /lesson {lesson.id}  -  {lesson.title}  [{prefix}]"

    def _normalize_search_text(self, value: str) -> str:
        return " ".join(value.lower().replace("-", " ").replace("_", " ").split())

    def _levenshtein_distance(self, left: str, right: str) -> int:
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

    def _open_suggestion_item(self, item: ListItem | None) -> None:
        if item is None or item.id is None:
            return
        try:
            slot = int(item.id.rsplit("-", 1)[1])
        except (IndexError, ValueError):
            return
        if 0 <= slot < len(self._visible_suggestion_indexes):
            self.app.push_screen(LessonScreen(LESSONS[self._visible_suggestion_indexes[slot]]))

    def _lesson_from_token(self, token: str):
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(LESSONS):
                return LESSONS[index]
        normalized = token.lower().replace(" ", "-")
        for lesson in LESSONS:
            if lesson.id == normalized or normalized in lesson.title.lower().replace(" ", "-"):
                return lesson
        return None
