"""Streamlit UI: the same product in two brand voices, compliance report, batch export, checker demo."""

from __future__ import annotations

import html
import json

import pandas as pd
import streamlit as st

from brand_voice.checker import RULE_LABELS, RULES, Finding, check, copy_fields, rule_status
from brand_voice.config import load_config
from brand_voice.data import load_brands, load_lexicon, load_products, load_seeded
from brand_voice.export import to_csv, to_json, to_rows
from brand_voice.llm import LLMError, unavailable_reason
from brand_voice.pipeline import Attempt, Result, from_dict, generate
from brand_voice.prompt import LANG_NAMES

st.set_page_config(page_title="Brand Voice Copywriter", layout="wide")

STATUS_STYLE = {  # label, text colour, background
    "pass": ("PASS", "#FFFFFF", "#2F6B4F"),
    "warning": ("WARNING", "#1F1B24", "#E8B04A"),
    "fail": ("FAIL", "#FFFFFF", "#B23A3A"),
}
MARK_STYLE = {
    "fail": "background:#F2C9C2;border-bottom:2px solid #B23A3A",
    "warning": "background:#F6E2B3;border-bottom:2px solid #E8B04A",
    "pass": "border-bottom:2px dotted #2F6B4F",
}


@st.cache_resource
def load_all():
    cfg = load_config()
    p = cfg["paths"]
    products = load_products(p["products"], p["schema"])
    brands = load_brands(p["brands"])
    lexicon = load_lexicon(p["claims"])
    samples = {}
    for path in sorted(p["samples"].glob("*.json")):
        with path.open(encoding="utf-8") as f:
            for d in json.load(f):
                samples[(d["sku"], d["brand"], d["lang"])] = d
    return cfg, products, brands, lexicon, load_seeded(p["seeded"]), samples


@st.cache_data(ttl=20, show_spinner=False)
def ollama_problem() -> str | None:
    return unavailable_reason(load_all()[0])


cfg, products, brands, lexicon, seeded, samples = load_all()
results: dict = st.session_state.setdefault("results", {})


# --- rendering helpers ---------------------------------------------------------------------------


def badge(status: str, text: str | None = None) -> str:
    label, fg, bg = STATUS_STYLE[status]
    return (
        f'<span style="background:{bg};color:{fg};padding:2px 8px;border-radius:10px;'
        f'font-size:0.75rem;font-weight:600;margin-right:6px;white-space:nowrap">'
        f"{html.escape(text or label)}</span>"
    )


def highlight(text: str, findings: list[Finding]) -> str:
    """Escape the text and wrap each finding's span in a coloured mark with the message as tooltip."""
    spans = sorted((f for f in findings if f.span), key=lambda f: (f.span[0], -f.span[1]))
    out, pos = [], 0
    for f in spans:
        start, end = f.span
        if start < pos:  # overlapping match: the first one wins
            continue
        out.append(html.escape(text[pos:start]))
        out.append(
            f'<span style="{MARK_STYLE[f.status]}" title="{html.escape(f.message)}">'
            f"{html.escape(text[start:end])}</span>"
        )
        pos = end
    out.append(html.escape(text[pos:]))
    return "".join(out)


def render_copy(attempt: Attempt) -> None:
    by_field = {
        name: [f for f in attempt.findings if f.field == name]
        for name, _ in copy_fields(attempt.copy)
    }
    fields = copy_fields(attempt.copy)
    title, description = fields[0][1], fields[1][1]
    bullets = "".join(f"<li>{highlight(t, by_field[n])}</li>" for n, t in fields[2:])
    st.markdown(
        f'<div style="background:#FFFFFF;border:1px solid #E2D8C9;border-radius:8px;padding:14px 18px">'
        f'<div style="font-size:1.15rem;font-weight:600;margin-bottom:6px">{highlight(title, by_field["title"])}</div>'
        f'<p style="margin:0 0 8px 0;line-height:1.55">{highlight(description, by_field["description"])}</p>'
        f'<ul style="margin:0">{bullets}</ul></div>',
        unsafe_allow_html=True,
    )


def render_report(attempt: Attempt) -> None:
    status = rule_status(attempt.findings)
    st.markdown(
        "".join(badge(status[r], f"{RULE_LABELS[r]}: {status[r]}") for r in RULES),
        unsafe_allow_html=True,
    )
    issues = [f for f in attempt.findings if f.status != "pass"]
    backed = [f for f in attempt.findings if f.status == "pass"]
    for f in issues:
        where = f"**{f.field}** · " if f.field else ""
        st.markdown(badge(f.status) + f"{where}{html.escape(f.message)}", unsafe_allow_html=True)
    if backed:
        st.caption(
            "Backed by the product record: "
            + ", ".join(sorted({f'"{f.text.lower()}"' for f in backed}))
        )


def render_result(result: Result, source: str) -> None:
    final = result.final
    times = " + ".join(f"{a.seconds:.1f} s" for a in result.attempts)
    when = "pre-generated" if source == "sample" else "generated live"
    note = f"{when} with `{result.model}` · {times}"
    if result.revised:
        note += " (first attempt + automatic revision)"
    st.markdown(badge(final.status, f"Overall: {final.status}"), unsafe_allow_html=True)
    st.caption(note)
    render_copy(final)
    render_report(final)
    if result.revised:
        with st.expander(f"First attempt ({result.attempts[0].status}) — revised automatically"):
            render_copy(result.attempts[0])
            render_report(result.attempts[0])


def get_result(
    sku: str, brand_id: str, lang: str, live: bool, create: bool
) -> tuple[Result | None, str]:
    """A live result from this session, else a pre-generated sample; generate it if asked and live."""
    key = (sku, brand_id, lang)
    if live and key in results:
        return results[key], "live"
    if live and create:
        results[key] = generate(products[sku], brand_id, brands[brand_id], lang, lexicon, cfg)
        return results[key], "live"
    if not live and key in samples:
        return from_dict(samples[key], products, brands, lexicon), "sample"
    return None, ""


# --- page ----------------------------------------------------------------------------------------

problem = ollama_problem()
with st.sidebar:
    st.markdown("### Brand Voice Copywriter")
    st.caption("Product data → on-brand copy in EN / IT / FR → deterministic compliance check.")
    live = st.toggle(
        "Generate live with the local model", value=problem is None, disabled=problem is not None
    )
    if live:
        st.success(f"Live: `{cfg['ollama']['model']}` via Ollama on this machine.")
    else:
        st.info("Showing pre-generated texts. The checker runs live on them.")
    st.divider()
    for b in brands.values():
        st.markdown(f"**{b['name']}** · {', '.join(b['tone'])}")
        st.caption(b["positioning"])

st.title("Brand Voice Copywriter")
st.markdown(
    "One product record, two brand voices, three languages. Every text is checked by plain rules "
    "(length, banned words, unsupported claims, language), and failing texts get **one automatic revision**."
)
if problem:
    st.warning(
        f"**Demo mode.** {problem} The app shows texts pre-generated with `{cfg['ollama']['model']}`; "
        "the compliance checker still runs live on them.\n\n"
        "To generate live: install Ollama from https://ollama.com/download, run "
        f"`ollama pull {cfg['ollama']['model']}`, then reload this page."
    )

tab_side, tab_batch, tab_checker = st.tabs(["Side by side", "Batch and export", "Checker demo"])

with tab_side:
    c1, c2 = st.columns([3, 2])
    sku = c1.selectbox(
        "Product", list(products), format_func=lambda s: f"{s} · {products[s]['name']}"
    )
    lang = c2.radio("Language", cfg["languages"], format_func=LANG_NAMES.get, horizontal=True)
    with st.expander("Product record (the only source of facts)"):
        st.json(products[sku])
    clicked = live and st.button("Generate with both brands", type="primary")
    cols = st.columns(len(brands))
    for col, (brand_id, brand) in zip(cols, brands.items(), strict=True):
        with col:
            st.subheader(brand["name"])
            try:
                with st.spinner(f"Writing as {brand['name']}… (the first call loads the model)"):
                    result, source = get_result(sku, brand_id, lang, live, clicked)
            except LLMError as e:
                st.error(str(e))
                continue
            if result:
                render_result(result, source)
            elif live:
                st.info("Click **Generate with both brands**.")
            else:
                st.info("No pre-generated text for this combination.")

with tab_batch:
    c1, c2 = st.columns(2)
    sel_brands = c1.multiselect(
        "Brands", list(brands), list(brands), format_func=lambda b: brands[b]["name"]
    )
    sel_langs = c2.multiselect(
        "Languages", cfg["languages"], cfg["languages"], format_func=LANG_NAMES.get
    )
    sel_skus = st.multiselect(
        "Products",
        list(products),
        list(products),
        format_func=lambda s: f"{s} · {products[s]['name']}",
    )
    jobs = [(s, b, lg) for b in sel_brands for s in sel_skus for lg in sel_langs]
    st.caption(
        f"{len(jobs)} texts." + (" Live generation takes a few seconds per text." if live else "")
    )
    if st.button("Run batch", type="primary", disabled=not jobs):
        batch, progress = [], st.progress(0.0)
        try:
            for i, (s, b, lg) in enumerate(jobs, 1):
                progress.progress(
                    i / len(jobs), text=f"{i}/{len(jobs)} · {brands[b]['name']} · {s} · {lg}"
                )
                result, _ = get_result(s, b, lg, live, create=True)
                if result:
                    batch.append(result)
        except LLMError as e:
            st.error(str(e))
        st.session_state["batch"] = batch
    batch = st.session_state.get("batch", [])
    if batch:
        rows = to_rows(batch, products)
        ok = sum(r["status"] != "fail" for r in rows)
        m1, m2, m3 = st.columns(3)
        m1.metric("Texts", len(rows))
        m2.metric("Compliant (no fail)", f"{ok}/{len(rows)}")
        m3.metric("Revised automatically", sum(r["revised"] for r in rows))
        shown = [
            "sku",
            "brand",
            "lang",
            "status",
            *(f"rule_{r}" for r in RULES),
            "revised",
            "title",
            "issues",
            "seconds",
        ]
        st.dataframe(pd.DataFrame(rows)[shown], hide_index=True, width="stretch")
        d1, d2 = st.columns(2)
        d1.download_button(
            "Download CSV", to_csv(batch, products), "brand_voice_copy.csv", "text/csv"
        )
        d2.download_button(
            "Download JSON", to_json(batch), "brand_voice_copy.json", "application/json"
        )

with tab_checker:
    st.markdown(
        "Hand-written texts with **deliberate violations**, to show what the checker catches. "
        "No model involved: these are plain rules from the brand files and `config/claims.yaml`."
    )
    ex = st.selectbox("Example", seeded, format_func=lambda e: e["label"])
    product = products[ex["sku"]]
    st.caption(
        f"{brands[ex['brand']]['name']} · {product['sku']} {product['name']} · requested language: "
        f"{LANG_NAMES[ex['lang']]} · materials: {', '.join(product['materials'])} · "
        f"sustainability attributes: {', '.join(product['sustainability_attrs']) or 'none'}"
    )
    attempt = Attempt(
        ex["copy"], 0.0, check(ex["copy"], product, brands[ex["brand"]], ex["lang"], lexicon)
    )
    st.markdown(badge(attempt.status, f"Overall: {attempt.status}"), unsafe_allow_html=True)
    render_copy(attempt)
    render_report(attempt)
