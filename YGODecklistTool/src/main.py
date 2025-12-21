from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional

from deck_io import export_cardmarket_wishlist, load_deck, save_deck
from deck_model import DeckEntry, DeckModel
from pdf_decklist import export_decklist_pdf
from pdf_overview import export_overview_pdf
from settings import load_settings, save_settings
from sort_utils import canonical_sort_entries, canonical_sort_key, rarity_rank_for_entry, section_rank
from yugioh_data import (
    get_card_by_id,
    get_card_by_name,
    is_extra_deck_monster,
    load_rarity_hierarchy_extra_side,
    load_rarity_hierarchy_main,
    search_card_names,
)

SECTIONS = ["Main", "Extra", "Side"]


class Autocomplete:
    def __init__(self, entry: ttk.Entry, on_select, colors: Dict[str, str]) -> None:
        self.entry = entry
        self.on_select = on_select
        self.popup = tk.Toplevel(entry)
        self.popup.withdraw()
        self.popup.overrideredirect(True)
        self.listbox = tk.Listbox(self.popup, height=10)
        self.listbox.configure(
            background=colors["entry_bg"],
            foreground=colors["fg"],
            selectbackground=colors["selection"],
            selectforeground=colors["fg"],
            highlightthickness=0,
            borderwidth=1,
        )
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._select)
        self.listbox.bind("<Return>", self._select)
        self.listbox.bind("<Escape>", lambda _event: self.hide())

    def show(self, items: List[str]) -> None:
        if not items:
            self.hide()
            return
        self.listbox.delete(0, tk.END)
        for item in items:
            self.listbox.insert(tk.END, item)
        x = self.entry.winfo_rootx()
        y = self.entry.winfo_rooty() + self.entry.winfo_height()
        self.popup.geometry(f"{self.entry.winfo_width()}x200+{x}+{y}")
        self.popup.deiconify()
        self.popup.lift()

    def hide(self) -> None:
        self.popup.withdraw()

    def _select(self, _event) -> None:
        selection = self.listbox.curselection()
        if not selection:
            return
        value = self.listbox.get(selection[0])
        self.on_select(value)
        self.hide()


class DeckApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("YGO Decklist Tool")
        self.model = DeckModel()
        self.settings = load_settings()
        self.current_sort_column: Optional[str] = None
        self.current_sort_desc = False
        self.db_available = True
        try:
            self.rarity_main = load_rarity_hierarchy_main()
            self.rarity_extra = load_rarity_hierarchy_extra_side()
        except FileNotFoundError as exc:
            messagebox.showwarning("Missing assets", str(exc))
            self.rarity_main = {}
            self.rarity_extra = {}

        self._apply_style()
        self._build_ui()
        geometry = self.settings.get("window_geometry")
        if geometry:
            self.root.geometry(geometry)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _apply_style(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")
        self._colors = {
            "bg": "#1e1e1e",
            "fg": "#f0f0f0",
            "accent": "#2d2d2d",
            "entry_bg": "#2b2b2b",
            "selection": "#3a6ea5",
            "header_bg": "#333333",
            "tree_bg": "#252525",
        }
        colors = self._colors
        self.root.configure(bg=colors["bg"])

        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        style.configure(
            "TButton",
            background=colors["accent"],
            foreground=colors["fg"],
            padding=6,
        )
        style.map(
            "TButton",
            background=[("active", "#3a3a3a")],
        )
        style.configure(
            "TEntry",
            fieldbackground=colors["entry_bg"],
            background=colors["entry_bg"],
            foreground=colors["fg"],
        )
        style.configure(
            "TCombobox",
            fieldbackground=colors["entry_bg"],
            background=colors["entry_bg"],
            foreground=colors["fg"],
        )
        style.configure(
            "TSpinbox",
            fieldbackground=colors["entry_bg"],
            background=colors["entry_bg"],
            foreground=colors["fg"],
        )
        style.configure("TLabelframe", background=colors["bg"], foreground=colors["fg"])
        style.configure(
            "TLabelframe.Label",
            background=colors["bg"],
            foreground=colors["fg"],
        )
        style.configure(
            "Treeview",
            background=colors["tree_bg"],
            fieldbackground=colors["tree_bg"],
            foreground=colors["fg"],
            rowheight=22,
            borderwidth=0,
        )
        style.configure(
            "Treeview.Heading",
            background=colors["header_bg"],
            foreground=colors["fg"],
            font=("Helvetica", 9, "bold"),
        )
        style.map(
            "Treeview",
            background=[("selected", colors["selection"])],
            foreground=[("selected", colors["fg"])],
        )

    def _build_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        columns = (
            "section",
            "amount",
            "name_eng",
            "name_ger",
            "card_id",
            "set_code",
            "rarity",
        )
        self.tree = ttk.Treeview(left_frame, columns=columns, show="headings", height=18)
        headings = [
            ("section", "Section"),
            ("amount", "Qty"),
            ("name_eng", "Name (ENG)"),
            ("name_ger", "Name (GER)"),
            ("card_id", "Card ID"),
            ("set_code", "Set ID"),
            ("rarity", "Rarity"),
        ]
        for col, label in headings:
            self.tree.heading(col, text=label, command=lambda c=col: self._sort_tree_by_column(c))
            self.tree.column(col, width=110 if col == "name_eng" else 80)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        counter_frame = ttk.Frame(left_frame)
        counter_frame.pack(fill=tk.X, pady=5)
        self.counter_label = ttk.Label(counter_frame, text="Main: 0 / Extra: 0 / Side: 0")
        self.counter_label.pack(anchor=tk.W)
        ttk.Button(counter_frame, text="Reset Sort", command=self._reset_sort).pack(anchor=tk.E, pady=2)

        form = ttk.LabelFrame(right_frame, text="Entry")
        form.pack(fill=tk.X, pady=5)

        ttk.Label(form, text="Section").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        default_section = self.settings.get("last_section", "Main")
        if default_section not in SECTIONS:
            default_section = "Main"
        self.section_var = tk.StringVar(value=default_section)
        self.section_combo = ttk.Combobox(form, textvariable=self.section_var, values=SECTIONS, state="readonly")
        self.section_combo.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        self.section_combo.bind("<<ComboboxSelected>>", self._on_section_change)

        ttk.Label(form, text="Name [ENG]").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.name_eng_var = tk.StringVar()
        self.name_eng_entry = ttk.Entry(form, textvariable=self.name_eng_var)
        self.name_eng_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        self.name_eng_entry.bind("<KeyRelease>", self._on_name_key)

        ttk.Label(form, text="Name [GER]").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.name_ger_var = tk.StringVar()
        self.name_ger_entry = ttk.Entry(form, textvariable=self.name_ger_var)
        self.name_ger_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(form, text="Card ID").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.card_id_var = tk.StringVar()
        card_id_frame = ttk.Frame(form)
        card_id_frame.grid(row=3, column=1, sticky=tk.EW, padx=5, pady=2)
        self.card_id_entry = ttk.Entry(card_id_frame, textvariable=self.card_id_var)
        self.card_id_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(card_id_frame, text="Lookup by ID", command=self._lookup_by_id).pack(side=tk.LEFT, padx=4)

        ttk.Label(form, text="Set ID").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.set_code_var = tk.StringVar()
        self.set_code_entry = ttk.Entry(form, textvariable=self.set_code_var)
        self.set_code_entry.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(form, text="Rarity").grid(row=5, column=0, sticky=tk.W, padx=5, pady=2)
        self.rarity_var = tk.StringVar()
        self.rarity_combo = ttk.Combobox(form, textvariable=self.rarity_var, values=[], state="readonly")
        self.rarity_combo.grid(row=5, column=1, sticky=tk.EW, padx=5, pady=2)

        ttk.Label(form, text="Amount").grid(row=6, column=0, sticky=tk.W, padx=5, pady=2)
        self.amount_var = tk.IntVar(value=1)
        self.amount_spin = ttk.Spinbox(form, from_=1, to=60, textvariable=self.amount_var, width=5)
        self.amount_spin.grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)

        form.columnconfigure(1, weight=1)

        actions = ttk.Frame(right_frame)
        actions.pack(fill=tk.X, pady=5)
        ttk.Button(actions, text="Add", command=self._add_entry).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Update", command=self._update_entry).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Delete", command=self._delete_entry).pack(fill=tk.X, pady=2)
        ttk.Button(actions, text="Clear", command=self._clear_form).pack(fill=tk.X, pady=2)

        exports = ttk.LabelFrame(right_frame, text="Export")
        exports.pack(fill=tk.X, pady=5)
        ttk.Button(exports, text="Export Decklist PDF", command=self._export_decklist).pack(fill=tk.X, pady=2)
        ttk.Button(exports, text="Export Overview PDF", command=self._export_overview).pack(fill=tk.X, pady=2)
        ttk.Button(
            exports,
            text="Export Cardmarket Wishlist TXT",
            command=self._export_cardmarket_wishlist,
        ).pack(fill=tk.X, pady=2)

        storage = ttk.LabelFrame(right_frame, text="Deck JSON")
        storage.pack(fill=tk.X, pady=5)
        ttk.Button(storage, text="Save Deck JSON", command=self._save_deck).pack(fill=tk.X, pady=2)
        ttk.Button(storage, text="Load Deck JSON", command=self._load_deck).pack(fill=tk.X, pady=2)

        header_frame = ttk.LabelFrame(right_frame, text="Header")
        header_frame.pack(fill=tk.X, pady=5)
        self.player_var = tk.StringVar()
        self.deck_name_var = tk.StringVar()
        self.event_var = tk.StringVar()
        ttk.Label(header_frame, text="Player").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(header_frame, textvariable=self.player_var).grid(row=0, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Label(header_frame, text="Deck Name").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(header_frame, textvariable=self.deck_name_var).grid(row=1, column=1, sticky=tk.EW, padx=5, pady=2)
        ttk.Label(header_frame, text="Event").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        ttk.Entry(header_frame, textvariable=self.event_var).grid(row=2, column=1, sticky=tk.EW, padx=5, pady=2)
        header_frame.columnconfigure(1, weight=1)

        colors = self._colors
        self.autocomplete = Autocomplete(self.name_eng_entry, self._select_autocomplete, colors)
        self._refresh_rarity_values()
        self._apply_canonical_sort()
        self._refresh_tree()

    def _get_card_from_form(self) -> Optional[dict]:
        if self.card_id_var.get().strip():
            try:
                return get_card_by_id(int(self.card_id_var.get().strip()))
            except ValueError:
                return None
        if self.name_eng_var.get().strip():
            return get_card_by_name(self.name_eng_var.get().strip())
        return None

    def _get_applicable_hierarchy(self) -> Dict[str, int]:
        section = self.section_var.get()
        if section == "Extra":
            return self.rarity_extra
        if section == "Side":
            card = self._get_card_from_form()
            if card and is_extra_deck_monster(card):
                return self.rarity_extra
        return self.rarity_main

    def _refresh_rarity_values(self) -> None:
        hierarchy = self._get_applicable_hierarchy()
        values = sorted(hierarchy.keys(), key=lambda k: hierarchy[k])
        self.rarity_combo["values"] = values
        if self.rarity_var.get() not in values:
            self.rarity_var.set(values[0] if values else "")

    def _persist_section(self) -> None:
        self.settings["last_section"] = self.section_var.get()
        save_settings(self.settings)

    def _on_section_change(self, _event) -> None:
        self._refresh_rarity_values()
        self._persist_section()

    def _on_name_key(self, _event) -> None:
        if not self.db_available:
            return
        text = self.name_eng_var.get()
        if not text:
            self.autocomplete.hide()
            return
        try:
            matches = search_card_names(text)
        except FileNotFoundError:
            self.db_available = False
            self.autocomplete.hide()
            return
        self.autocomplete.show(matches)

    def _select_autocomplete(self, value: str) -> None:
        self.name_eng_var.set(value)
        try:
            card = get_card_by_name(value)
        except FileNotFoundError:
            self.db_available = False
            card = None
        if card:
            self.card_id_var.set(str(card.get("id", "")))
        self._refresh_rarity_values()

    def _lookup_by_id(self) -> None:
        if not self.db_available:
            messagebox.showwarning("Card DB missing", "Card database not available.")
            return
        try:
            card_id = int(self.card_id_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid ID", "Card ID must be a number.")
            return
        try:
            card = get_card_by_id(card_id)
        except FileNotFoundError:
            self.db_available = False
            messagebox.showwarning("Card DB missing", "Card database not available.")
            return
        if not card:
            messagebox.showerror("Not found", "Card ID not found in database.")
            return
        self.name_eng_var.set(card.get("name", ""))
        self._refresh_rarity_values()

    def _entry_from_form(self) -> Optional[DeckEntry]:
        name_eng = self.name_eng_var.get().strip()
        if not name_eng:
            messagebox.showerror("Missing name", "Name [ENG] is required.")
            return None
        return DeckEntry(
            section=self.section_var.get(),
            amount=int(self.amount_var.get()),
            name_eng=name_eng,
            name_ger=self.name_ger_var.get().strip(),
            card_id=self.card_id_var.get().strip(),
            set_code=self.set_code_var.get().strip(),
            rarity=self.rarity_var.get().strip(),
        )

    def _add_entry(self) -> None:
        entry = self._entry_from_form()
        if not entry:
            return
        self.model.add_entry(entry)
        self._apply_canonical_sort()
        self._reset_sort()
        self._clear_form()

    def _update_entry(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("Select entry", "Select an entry to update.")
            return
        entry = self._entry_from_form()
        if not entry:
            return
        index = int(selection[0])
        self.model.update_entry(index, entry)
        self._apply_canonical_sort()
        self._reset_sort()

    def _delete_entry(self) -> None:
        selection = self.tree.selection()
        if not selection:
            messagebox.showerror("Select entry", "Select an entry to delete.")
            return
        index = int(selection[0])
        self.model.delete_entry(index)
        self._apply_canonical_sort()
        self._reset_sort()
        self._clear_form()

    def _clear_form(self) -> None:
        self.name_eng_var.set("")
        self.name_ger_var.set("")
        self.card_id_var.set("")
        self.set_code_var.set("")
        self.rarity_var.set("")
        self.amount_var.set(1)
        self._refresh_rarity_values()

    def _populate_tree(self, ordered_entries: List[tuple[int, DeckEntry]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for idx, entry in ordered_entries:
            self.tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    entry.section,
                    entry.amount,
                    entry.name_eng,
                    entry.name_ger,
                    entry.card_id,
                    entry.set_code,
                    entry.rarity,
                ),
            )

    def _refresh_tree(self) -> None:
        self._populate_tree(list(enumerate(self.model.entries)))
        counts = self.model.counts()
        self.counter_label.config(
            text=f"Main: {counts['Main']} / Extra: {counts['Extra']} / Side: {counts['Side']}"
        )

    def _on_tree_select(self, _event) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        entry = self.model.get_entry(int(selection[0]))
        if not entry:
            return
        self.section_var.set(entry.section)
        self.name_eng_var.set(entry.name_eng)
        self.name_ger_var.set(entry.name_ger)
        self.card_id_var.set(entry.card_id)
        self.set_code_var.set(entry.set_code)
        self.rarity_var.set(entry.rarity)
        self.amount_var.set(entry.amount)
        self._refresh_rarity_values()
        self._persist_section()

    def _apply_canonical_sort(self) -> None:
        self.model.entries = canonical_sort_entries(self.model.entries)

    def _reset_sort(self) -> None:
        self.current_sort_column = None
        self.current_sort_desc = False
        self._apply_canonical_sort()
        self._refresh_tree()

    def _sort_tree_by_column(self, column: str) -> None:
        if self.current_sort_column == column:
            self.current_sort_desc = not self.current_sort_desc
        else:
            self.current_sort_column = column
            self.current_sort_desc = False

        def lookup_card(entry: DeckEntry) -> Optional[dict]:
            if entry.card_id:
                try:
                    return get_card_by_id(int(entry.card_id))
                except (ValueError, FileNotFoundError):
                    return None
            if entry.name_eng:
                try:
                    return get_card_by_name(entry.name_eng)
                except FileNotFoundError:
                    return None
            return None

        def sort_key(item: tuple[int, DeckEntry]) -> tuple:
            _, entry = item
            if column == "amount":
                return (entry.amount,)
            if column == "section":
                return canonical_sort_key(entry)
            if column == "rarity":
                return (rarity_rank_for_entry(entry, lookup_card(entry)), entry.rarity.casefold())
            if column == "name_eng":
                return (entry.name_eng.casefold(),)
            if column == "name_ger":
                return (entry.name_ger.casefold(),)
            if column == "card_id":
                return (entry.card_id.casefold(),)
            if column == "set_code":
                return (entry.set_code.casefold(),)
            return canonical_sort_key(entry)

        ordered_entries = sorted(
            list(enumerate(self.model.entries)),
            key=sort_key,
            reverse=self.current_sort_desc,
        )
        self._populate_tree(ordered_entries)

    def _export_decklist(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        header = {
            "player_name": self.player_var.get().strip(),
            "deck_name": self.deck_name_var.get().strip(),
            "event_name": self.event_var.get().strip(),
        }
        try:
            export_decklist_pdf(path, header, self.model.entries)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Exported", f"Saved decklist to {path}")

    def _export_overview(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF", "*.pdf")],
        )
        if not path:
            return
        header = {
            "player_name": self.player_var.get().strip(),
            "deck_name": self.deck_name_var.get().strip(),
            "event_name": self.event_var.get().strip(),
        }
        try:
            export_overview_pdf(path, header, self.model.entries)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Exported", f"Saved overview to {path}")

    def _export_cardmarket_wishlist(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text", "*.txt")],
        )
        if not path:
            return
        try:
            payload = export_cardmarket_wishlist(self.model.entries)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(payload)
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Exported", f"Saved wishlist import text to {path}")

    def _save_deck(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
        )
        if not path:
            return
        header = {
            "player_name": self.player_var.get().strip(),
            "deck_name": self.deck_name_var.get().strip(),
            "event_name": self.event_var.get().strip(),
        }
        try:
            save_deck(path, header, self.model.entries)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        messagebox.showinfo("Saved", f"Saved deck to {path}")

    def _load_deck(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            header, entries = load_deck(path)
        except Exception as exc:
            messagebox.showerror("Load failed", str(exc))
            return
        self.player_var.set(header.get("player_name", ""))
        self.deck_name_var.set(header.get("deck_name", ""))
        self.event_var.set(header.get("event_name", ""))
        self.model.entries = entries
        self._apply_canonical_sort()
        self._reset_sort()
        messagebox.showinfo("Loaded", f"Loaded deck from {path}")

    def _on_close(self) -> None:
        self.settings["window_geometry"] = self.root.winfo_geometry()
        save_settings(self.settings)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    app = DeckApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
