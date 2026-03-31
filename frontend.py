import tkinter as tk
from tkinter import messagebox

from phase1 import (
    lex,
    Parser,
    CodeGenerator,
    optimize_instructions,
    format_tokens,
    format_ast,
    format_instructions,
)
from phase3 import perform_semantic_analysis

# Layout / theme
BG_APP = "#1a1d23"
BG_PANEL = "#252830"
BG_TITLE = "#2f3540"
BG_TEXT = "#1e2229"
FG_TEXT = "#e6e8ef"
FG_MUTED = "#9aa3b2"
ACCENT = "#3d9eff"
ACCENT_DIM = "#4a5568"
HIGHLIGHT_BORDER = "#3d9eff"
HIGHLIGHT_TITLE = "#2563a8"
HIGHLIGHT_PANEL = "#1a3048"


class CompilerFrontend(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Intermediate Code Generator - Visual Pipeline")
        self.geometry("1320x780")
        self.minsize(1080, 640)
        self.configure(bg=BG_APP)

        # Per-phase default border (subtle variety)
        self._phase_border_idle = ["#4a5568", "#5c6570", "#4a5568", "#5c6570"]
        self._build_ui()

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg=BG_APP)
        header.pack(fill="x", padx=28, pady=(18, 8))

        title = tk.Label(
            header,
            text="Intermediate Code Generator",
            font=("Segoe UI", 22, "bold"),
            fg="#ffffff",
            bg=BG_APP,
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            header,
            text="Watch each phase as your expression moves through the compiler pipeline",
            font=("Segoe UI", 12),
            fg=FG_MUTED,
            bg=BG_APP,
        )
        subtitle.pack(anchor="w", pady=(6, 0))

        input_frame = tk.Frame(self, bg=BG_APP)
        input_frame.pack(fill="x", padx=28, pady=(12, 8))

        input_label = tk.Label(
            input_frame,
            text="Source input:",
            font=("Segoe UI", 11),
            fg="#ffffff",
            bg=BG_APP,
        )
        input_label.pack(side="left")

        self.input_entry = tk.Entry(
            input_frame,
            font=("Consolas", 12),
            bg=BG_TEXT,
            fg=FG_TEXT,
            insertbackground=ACCENT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=ACCENT_DIM,
            highlightcolor=ACCENT,
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(12, 12), ipady=8)

        run_button = tk.Button(
            input_frame,
            text="Run pipeline",
            font=("Segoe UI", 11, "bold"),
            bg=ACCENT,
            fg="#ffffff",
            activebackground="#2b7fd4",
            activeforeground="#ffffff",
            relief="flat",
            padx=22,
            pady=10,
            cursor="hand2",
            command=self.run_pipeline,
        )
        run_button.pack(side="left")

        # Main phases: each column expands
        phases_frame = tk.Frame(self, bg=BG_APP)
        phases_frame.pack(fill="both", expand=True, padx=24, pady=(8, 12))
        phases_frame.grid_rowconfigure(0, weight=1)
        for c in range(5):
            phases_frame.grid_columnconfigure(c, weight=1, uniform="phase")

        self.phase_boxes: list[tuple[tk.Frame, tk.Label, tk.Text]] = []
        phase_titles = [
            "PHASE 1\nLexical Analysis",
            "PHASE 2\nSyntax & AST",
            "PHASE 3\nSemantic Analysis",
            "PHASE 4\nIntermediate Code Generated",
            "PHASE 5\nCode Optimization",
        ]

        for idx, title_text in enumerate(phase_titles):
            border = self._phase_border_idle[idx % len(self._phase_border_idle)]
            frame = tk.Frame(
                phases_frame,
                bg=BG_PANEL,
                highlightbackground=border,
                highlightthickness=2,
                bd=0,
            )
            frame.grid(row=0, column=idx, padx=10, pady=6, sticky="nsew")

            title_label = tk.Label(
                frame,
                text=title_text,
                font=("Segoe UI", 12, "bold"),
                fg="#ffffff",
                bg=BG_TITLE,
                anchor="center",
                pady=12,
                padx=10,
            )
            title_label.pack(fill="x")

            content = tk.Text(
                frame,
                font=("Consolas", 11),
                bg=BG_TEXT,
                fg=FG_TEXT,
                wrap="word",
                height=28,
                borderwidth=0,
                highlightthickness=0,
                padx=14,
                pady=14,
                state="disabled",
            )
            content.pack(fill="both", expand=True, padx=10, pady=(0, 12))

            self.phase_boxes.append((frame, title_label, content))

        self.status_label = tk.Label(
            self,
            text="Ready.",
            font=("Segoe UI", 10),
            fg=FG_MUTED,
            bg=BG_APP,
            anchor="w",
        )
        self.status_label.pack(fill="x", padx=28, pady=(0, 14))

    def clear_boxes(self) -> None:
        for i, (frame, title, content) in enumerate(self.phase_boxes):
            border = self._phase_border_idle[i % len(self._phase_border_idle)]
            frame.configure(bg=BG_PANEL, highlightbackground=border, highlightthickness=2)
            title.configure(bg=BG_TITLE)
            content.configure(state="normal")
            content.delete("1.0", tk.END)
            content.configure(state="disabled")

    def highlight_box(self, index: int) -> None:
        for i, (frame, title, _) in enumerate(self.phase_boxes):
            if i == index:
                frame.configure(bg=HIGHLIGHT_PANEL, highlightbackground=HIGHLIGHT_BORDER, highlightthickness=3)
                title.configure(bg=HIGHLIGHT_TITLE)
            else:
                border = self._phase_border_idle[i % len(self._phase_border_idle)]
                frame.configure(bg=BG_PANEL, highlightbackground=border, highlightthickness=2)
                title.configure(bg=BG_TITLE)

    def set_box_content(self, index: int, text: str) -> None:
        _, _, content = self.phase_boxes[index]
        content.configure(state="normal")
        content.delete("1.0", tk.END)
        content.insert(tk.END, text)
        content.configure(state="disabled")

    def run_pipeline(self) -> None:
        source = self.input_entry.get().strip()
        if not source:
            messagebox.showwarning("No input", "Please enter an expression or statements first.")
            return

        try:
            self.clear_boxes()
            self.status_label.configure(text="Running pipeline...")

            tokens = lex(source)
            tokens_text = format_tokens(tokens)

            parser = Parser(tokens)
            ast = parser.parse()
            ast_text = format_ast(ast)

            # Semantic Analysis Phase
            semantic_errors = perform_semantic_analysis(ast)
            if semantic_errors:
                semantic_text = "Semantic Errors Found:\n" + "\n".join(f"• {error}" for error in semantic_errors)
            else:
                semantic_text = "Semantic Analysis: No errors found\n\nAll variables properly declared and used."

            codegen = CodeGenerator()
            raw_instructions, _ = codegen.generate(ast)
            code_text = format_instructions(raw_instructions)

            optimized_instructions = optimize_instructions(raw_instructions)
            optimized_text = format_instructions(optimized_instructions)

            steps = [
                (0, f"=== SOURCE TEXT ===\n{source}\n\n{tokens_text}"),
                (1, f"AST:\n{ast_text}"),
                (2, f"{semantic_text}"),
                (3, f"Three-address code:\n{code_text}"),
                (4, f"Optimized three-address code:\n{optimized_text}"),
            ]

            delay_ms = 600

            def make_step_callback(idx: int, text: str):
                def _cb() -> None:
                    self.highlight_box(idx)
                    self.set_box_content(idx, text)
                    title_widget = self.phase_boxes[idx][1]
                    self.status_label.configure(text=f"Showing: {title_widget.cget('text')}")

                return _cb

            for i, (idx, text) in enumerate(steps):
                self.after(i * delay_ms, make_step_callback(idx, text))

            self.after(
                len(steps) * delay_ms + 50,
                lambda: self.status_label.configure(text="Pipeline complete."),
            )

        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Error", f"An error occurred:\n{e}")
            self.status_label.configure(text="Error during pipeline.")


def main() -> None:
    app = CompilerFrontend()
    app.mainloop()


if __name__ == "__main__":
    main()
