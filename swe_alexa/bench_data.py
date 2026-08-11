"""Load non-code benchmark slices for Alexa-Rufus-1 evals."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any, Callable

from datasets import load_dataset

# Balanced sample sizes (time vs signal) for ~2 parallel Rufus workers.
DEFAULT_LIMITS: dict[str, int] = {
    "mmlu_pro": 80,
    "arc_challenge": 80,
    "openbookqa": 80,
    "gsm8k": 80,
    "truthfulqa_mc": 80,
    "simpleqa": 60,
    "shopping_mc": 40,
}

SUITE_ORDER = [
    "mmlu_pro",
    "arc_challenge",
    "openbookqa",
    "gsm8k",
    "truthfulqa_mc",
    "simpleqa",
    "shopping_mc",
]


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def _take(rows: list[dict[str, Any]], limit: int | None, seed: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    indexed = list(enumerate(rows))
    rng.shuffle(indexed)
    if limit is not None:
        indexed = indexed[:limit]
    out: list[dict[str, Any]] = []
    for new_i, (_, row) in enumerate(indexed):
        r = dict(row)
        r["idx"] = new_i
        out.append(r)
    return out


def load_mmlu_pro(limit: int | None = 80, seed: int = 0) -> list[dict[str, Any]]:
    ds = load_dataset("TIGER-Lab/MMLU-Pro", split="test")
    rows = []
    for i, ex in enumerate(ds):
        opts = [str(o) for o in list(ex["options"]) if str(o).strip()]
        if len(opts) < 2:
            continue
        ans = ex.get("answer")
        letters_full = "ABCDEFGHIJ"
        if isinstance(ans, int):
            if ans < 0 or ans >= len(opts):
                continue
            correct = opts[ans]
        else:
            letter = str(ans).strip().upper()
            if letter in letters_full[: len(opts)]:
                correct = opts[letters_full.index(letter)]
            elif str(ans) in opts:
                correct = str(ans)
            else:
                continue
        rng = random.Random(seed + i * 13)
        if len(opts) > 4:
            others = [o for o in opts if o != correct]
            pick = rng.sample(others, min(3, len(others)))
            choices = [correct, *pick]
        else:
            choices = list(opts)
        rng.shuffle(choices)
        # pad/truncate to <=4
        choices = choices[:4]
        if correct not in choices:
            choices[0] = correct
            rng.shuffle(choices)
        correct_letter = "ABCD"[choices.index(correct)]
        rows.append(
            {
                "record_id": f"mmlu_pro_{i}",
                "benchmark": "mmlu_pro",
                "format": "mc",
                "question": _norm_ws(ex["question"]),
                "choices": choices,
                "correct_letter": correct_letter,
                "correct_answer": correct,
                "domain": str(ex.get("category") or ""),
            }
        )
    return _take(rows, limit, seed)


def load_arc_challenge(limit: int | None = 80, seed: int = 0) -> list[dict[str, Any]]:
    ds = load_dataset("allenai/ai2_arc", "ARC-Challenge", split="test")
    rows = []
    for i, ex in enumerate(ds):
        labels = list(ex["choices"]["label"])
        texts = list(ex["choices"]["text"])
        key = str(ex["answerKey"]).strip().upper()
        # Normalize 1-4 keys to A-D
        if key.isdigit():
            key = "ABCD"[int(key) - 1]
        mapping = {lab.upper(): txt for lab, txt in zip(labels, texts)}
        # Build A-D list in label order remapped
        ordered = []
        for lab, txt in zip(labels, texts):
            ordered.append(txt)
        # Ensure 4 or fewer
        if key not in mapping:
            continue
        correct = mapping[key]
        # shuffle into A-D
        rng = random.Random(seed + i * 7)
        choices = list(ordered[:4])
        if correct not in choices:
            choices = [correct, *[t for t in ordered if t != correct][:3]]
        rng.shuffle(choices)
        correct_letter = "ABCD"[choices.index(correct)]
        rows.append(
            {
                "record_id": str(ex.get("id") or f"arc_{i}"),
                "benchmark": "arc_challenge",
                "format": "mc",
                "question": _norm_ws(ex["question"]),
                "choices": choices,
                "correct_letter": correct_letter,
                "correct_answer": correct,
                "domain": "science",
            }
        )
    return _take(rows, limit, seed)


def load_openbookqa(limit: int | None = 80, seed: int = 0) -> list[dict[str, Any]]:
    ds = load_dataset("allenai/openbookqa", "main", split="test")
    rows = []
    for i, ex in enumerate(ds):
        labels = list(ex["choices"]["label"])
        texts = list(ex["choices"]["text"])
        key = str(ex["answerKey"]).strip().upper()
        mapping = {lab.upper(): txt for lab, txt in zip(labels, texts)}
        correct = mapping[key]
        rng = random.Random(seed + i * 11)
        choices = list(texts[:4])
        rng.shuffle(choices)
        correct_letter = "ABCD"[choices.index(correct)]
        rows.append(
            {
                "record_id": str(ex.get("id") or f"obqa_{i}"),
                "benchmark": "openbookqa",
                "format": "mc",
                "question": _norm_ws(ex["question_stem"]),
                "choices": choices,
                "correct_letter": correct_letter,
                "correct_answer": correct,
                "domain": "science",
            }
        )
    return _take(rows, limit, seed)


def _gsm8k_gold(answer_field: str) -> str:
    # openai gsm8k answers end with #### <number>
    m = re.search(r"####\s*(.+)\s*$", answer_field.strip())
    raw = m.group(1) if m else answer_field.strip().split("\n")[-1]
    raw = raw.replace(",", "").strip()
    return raw


def load_gsm8k(limit: int | None = 80, seed: int = 0) -> list[dict[str, Any]]:
    ds = load_dataset("openai/gsm8k", "main", split="test")
    rows = []
    for i, ex in enumerate(ds):
        gold = _gsm8k_gold(ex["answer"])
        rows.append(
            {
                "record_id": f"gsm8k_{i}",
                "benchmark": "gsm8k",
                "format": "numeric",
                "question": _norm_ws(ex["question"]),
                "choices": [],
                "correct_letter": "",
                "correct_answer": gold,
                "domain": "math",
            }
        )
    return _take(rows, limit, seed)


def load_truthfulqa_mc(limit: int | None = 80, seed: int = 0) -> list[dict[str, Any]]:
    ds = load_dataset("truthfulqa/truthful_qa", "multiple_choice", split="validation")
    rows = []
    for i, ex in enumerate(ds):
        targets = ex["mc1_targets"]
        choices = list(targets["choices"])
        labels = list(targets["labels"])
        # labels 1 = correct
        correct_idxs = [j for j, lab in enumerate(labels) if int(lab) == 1]
        if not correct_idxs:
            continue
        correct = choices[correct_idxs[0]]
        rng = random.Random(seed + i * 19)
        # keep correct + up to 3 incorrect
        incorrect = [c for j, c in enumerate(choices) if j not in correct_idxs]
        pick = rng.sample(incorrect, min(3, len(incorrect)))
        opts = [correct, *pick]
        rng.shuffle(opts)
        correct_letter = "ABCD"[opts.index(correct)]
        rows.append(
            {
                "record_id": f"tqa_{i}",
                "benchmark": "truthfulqa_mc",
                "format": "mc",
                "question": _norm_ws(ex["question"]),
                "choices": opts,
                "correct_letter": correct_letter,
                "correct_answer": correct,
                "domain": "truthfulness",
            }
        )
    return _take(rows, limit, seed)


def load_simpleqa(limit: int | None = 60, seed: int = 0) -> list[dict[str, Any]]:
    # Prefer a public SimpleQA mirror
    last_err: Exception | None = None
    ds = None
    for name, split in [
        ("basicv8vc/SimpleQA", "test"),
        ("basicv8vc/SimpleQA", "train"),
        ("lighteval/SimpleQA", "test"),
    ]:
        try:
            ds = load_dataset(name, split=split)
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
    if ds is None:
        raise RuntimeError(f"Could not load SimpleQA: {last_err}")
    rows = []
    for i, ex in enumerate(ds):
        q = ex.get("problem") or ex.get("question") or ex.get("prompt")
        a = ex.get("answer") or ex.get("gold") or ex.get("target")
        if not q or a is None:
            continue
        rows.append(
            {
                "record_id": str(ex.get("id") or f"simpleqa_{i}"),
                "benchmark": "simpleqa",
                "format": "short",
                "question": _norm_ws(q),
                "choices": [],
                "correct_letter": "",
                "correct_answer": _norm_ws(a),
                "domain": str(ex.get("metadata", {}).get("topic") if isinstance(ex.get("metadata"), dict) else "")
                or "factual",
            }
        )
    return _take(rows, limit, seed)


SHOPPING_ITEMS: list[dict[str, Any]] = [
    {
        "q": "What does Amazon Prime typically include for eligible items in the US?",
        "correct": "Fast free shipping and Prime Video access",
        "wrong": ["Only bookstore discounts", "Free gasoline", "Unlimited grocery robots"],
        "domain": "prime",
    },
    {
        "q": "On Amazon product pages, what do customer star ratings mainly reflect?",
        "correct": "Buyer reviews of the product",
        "wrong": ["Warehouse employee scores", "Seller credit scores", "Shipping truck speed only"],
        "domain": "reviews",
    },
    {
        "q": "What is a common meaning of 'Add to Cart' on Amazon?",
        "correct": "Save the item to buy later in checkout",
        "wrong": ["Delete the listing", "Subscribe permanently", "Message the CEO"],
        "domain": "cart",
    },
    {
        "q": "What is Amazon's 'Subscribe & Save' mainly for?",
        "correct": "Recurring deliveries of consumable items",
        "wrong": ["One-time flash auctions", "Selling used cars only", "Canceling Prime forever"],
        "domain": "subscribe",
    },
    {
        "q": "Which category is most related to buying a laptop?",
        "correct": "Electronics / Computers",
        "wrong": ["Fresh produce only", "Pet grooming only", "Lawn soil only"],
        "domain": "category",
    },
    {
        "q": "What does 'Fulfilled by Amazon' often indicate?",
        "correct": "Amazon stores and ships the item",
        "wrong": ["Item is a digital NFT", "Seller must hand-deliver same hour", "Product is free forever"],
        "domain": "fba",
    },
    {
        "q": "A gift card for Amazon is primarily used to:",
        "correct": "Pay for eligible Amazon purchases",
        "wrong": ["Unlock phone SIM cards", "Pay property taxes", "Replace a passport"],
        "domain": "giftcard",
    },
    {
        "q": "What is a wishlist on Amazon for?",
        "correct": "Saving items you may want later or share",
        "wrong": ["Deleting seller accounts", "Filing tax returns", "Booking airline seats"],
        "domain": "wishlist",
    },
    {
        "q": "If an item shows 'In Stock', it usually means:",
        "correct": "It is available to purchase now",
        "wrong": ["It is discontinued forever", "It can only be rented", "It requires a prescription always"],
        "domain": "stock",
    },
    {
        "q": "Amazon Returns typically start from:",
        "correct": "Your orders page / returns center",
        "wrong": ["Social media comments only", "Postal lottery", "Calling a radio station"],
        "domain": "returns",
    },
    {
        "q": "Which is the best first step to track a package?",
        "correct": "Check Order Details / tracking link",
        "wrong": ["Reinstall the OS", "Buy a new router always", "Ignore delivery emails"],
        "domain": "tracking",
    },
    {
        "q": "A product filter for '4 Stars & Up' mainly keeps:",
        "correct": "Higher-rated items",
        "wrong": ["Only free samples", "Only damaged goods", "Only books from 1800"],
        "domain": "filters",
    },
    {
        "q": "What is 'Buy Now' intended to do?",
        "correct": "Start checkout quickly for that item",
        "wrong": ["Erase your cart history", "Create a storefront", "Open a bank account"],
        "domain": "buynow",
    },
    {
        "q": "ASIN on Amazon refers to:",
        "correct": "A unique product identifier",
        "wrong": ["A shipping truck model", "A Prime movie genre", "A warehouse city code only"],
        "domain": "asin",
    },
    {
        "q": "Which item is most likely a consumable for Subscribe & Save?",
        "correct": "Coffee pods or paper towels",
        "wrong": ["A single house deed", "A one-of-a-kind painting always", "A live concert ticket only"],
        "domain": "consumable",
    },
    {
        "q": "Amazon Fresh is mainly about:",
        "correct": "Grocery and perishable delivery",
        "wrong": ["Only used textbooks", "Only industrial steel", "Only concert tickets"],
        "domain": "fresh",
    },
    {
        "q": "If two sellers offer the same item, price and shipping may differ because:",
        "correct": "Different sellers set offers and fulfillment",
        "wrong": ["ASIN changes every minute", "Reviews delete pricing", "Cart ignores sellers"],
        "domain": "offers",
    },
    {
        "q": "A 'Lightning Deal' is typically:",
        "correct": "A time-limited discounted offer",
        "wrong": ["A permanent list price forever", "A tax form", "A return label only"],
        "domain": "deals",
    },
    {
        "q": "Customer Q&A on a product page is mainly for:",
        "correct": "Shopper questions about the product",
        "wrong": ["Filing lawsuits", "Changing warehouse robots", "Setting national interest rates"],
        "domain": "qa",
    },
    {
        "q": "Which accessory commonly pairs with a DSLR camera purchase?",
        "correct": "Memory card / extra battery",
        "wrong": ["Garden hose nozzle", "Cat litter only", "Oven mitt set only"],
        "domain": "attach",
    },
    {
        "q": "What should you check before buying apparel online?",
        "correct": "Size chart and return policy",
        "wrong": ["Only the warehouse ZIP", "Seller shoe size", "Driver license barcode"],
        "domain": "apparel",
    },
    {
        "q": "Amazon Pantry-style grocery boxes historically focused on:",
        "correct": "Shelf-stable household groceries",
        "wrong": ["Only live animals", "Only real estate listings", "Only airline miles"],
        "domain": "grocery",
    },
    {
        "q": "A 'climate pledge friendly' badge relates to:",
        "correct": "Sustainability / climate certifications",
        "wrong": ["Faster GPU clocks", "Larger pizza toppings", "Free concert tickets"],
        "domain": "sustainability",
    },
    {
        "q": "If a listing says 'Used - Like New', condition is:",
        "correct": "Pre-owned but described as nearly new",
        "wrong": ["Brand-new sealed factory only", "Broken for parts only", "Digital download only"],
        "domain": "condition",
    },
    {
        "q": "Price drop alerts / watchlists help you:",
        "correct": "Notice when an item gets cheaper",
        "wrong": ["Delete your profile", "Change tax residency", "Hack seller accounts"],
        "domain": "price",
    },
    {
        "q": "Which is a sensible gift for a new coffee drinker?",
        "correct": "A coffee maker or bean grinder",
        "wrong": ["A snowmobile track only", "Industrial rebar", "A single unlabeled key"],
        "domain": "gifting",
    },
    {
        "q": "Amazon Basics typically refers to:",
        "correct": "Amazon’s private-label everyday products",
        "wrong": ["Only luxury jewelry", "Government bonds", "Airline cockpit parts"],
        "domain": "basics",
    },
    {
        "q": "Two-day delivery estimates depend most on:",
        "correct": "Address, stock, and membership/fulfillment",
        "wrong": ["Your browser theme color", "Phone case pattern", "Desktop wallpaper"],
        "domain": "delivery",
    },
    {
        "q": "A product 'variation' (size/color) means:",
        "correct": "Different options of the same parent item",
        "wrong": ["A different website domain", "A tax category only", "A returned empty box"],
        "domain": "variation",
    },
    {
        "q": "Best practice before buying electronics:",
        "correct": "Check specs, compatibility, and reviews",
        "wrong": ["Ignore voltage and plugs", "Only read the ad headline", "Skip return windows always"],
        "domain": "electronics",
    },
    {
        "q": "What is a seller 'feedback' score mainly about?",
        "correct": "Buyer ratings of seller transactions",
        "wrong": ["UPS truck paint color", "Prime Video ratings only", "Warehouse temperature"],
        "domain": "seller",
    },
    {
        "q": "An extended warranty offer at checkout is:",
        "correct": "Optional protection plan for some items",
        "wrong": ["Mandatory for all bananas", "A replacement for Prime", "A shipping label format"],
        "domain": "warranty",
    },
    {
        "q": "Which filter helps find vegan grocery options?",
        "correct": "Dietary / vegan attribute filters",
        "wrong": ["GPU VRAM filters", "Tire tread filters", "Lens aperture only"],
        "domain": "dietary",
    },
    {
        "q": "A 'bundle' listing usually means:",
        "correct": "Multiple items sold together",
        "wrong": ["A single broken spare part", "An empty category", "A canceled order only"],
        "domain": "bundle",
    },
    {
        "q": "If you need a last-minute birthday gift under $25, you should prioritize:",
        "correct": "In-stock items with fast delivery",
        "wrong": ["Out-of-stock collectibles only", "Items with 3-month shipping only", "Untrackable freight pallets"],
        "domain": "gifting",
    },
    {
        "q": "Amazon Pharmacy is related to:",
        "correct": "Prescription and health-care products",
        "wrong": ["Only video games", "Only lawn tractors", "Only concert venues"],
        "domain": "pharmacy",
    },
    {
        "q": "Comparing 'similar items' widgets helps you:",
        "correct": "Discover alternatives and price options",
        "wrong": ["Reset your password", "Change your legal name", "Delete order history forever"],
        "domain": "compare",
    },
    {
        "q": "A high return rate on apparel often relates to:",
        "correct": "Sizing and fit uncertainty",
        "wrong": ["ASIN being too short", "Cart button color", "Wishlist icons"],
        "domain": "apparel",
    },
    {
        "q": "What is the main purpose of product photos?",
        "correct": "Show appearance and details to shoppers",
        "wrong": ["Train delivery drones only", "Replace customer service chats", "Set income tax brackets"],
        "domain": "photos",
    },
    {
        "q": "If Alexa helps while shopping, a typical useful ask is:",
        "correct": "Compare options or find gifts in a budget",
        "wrong": ["Compile a Linux kernel patch", "Rewrite a GitHub PR diff", "Prove P=NP"],
        "domain": "rufus",
    },
]


def load_shopping_mc(limit: int | None = 40, seed: int = 0) -> list[dict[str, Any]]:
    rows = []
    for i, item in enumerate(SHOPPING_ITEMS):
        rng = random.Random(seed + i * 23)
        choices = [item["correct"], *item["wrong"][:3]]
        rng.shuffle(choices)
        rows.append(
            {
                "record_id": f"shop_{i}",
                "benchmark": "shopping_mc",
                "format": "mc",
                "question": item["q"],
                "choices": choices,
                "correct_letter": "ABCD"[choices.index(item["correct"])],
                "correct_answer": item["correct"],
                "domain": item["domain"],
            }
        )
    return _take(rows, limit, seed)


LOADERS: dict[str, Callable[..., list[dict[str, Any]]]] = {
    "mmlu_pro": load_mmlu_pro,
    "arc_challenge": load_arc_challenge,
    "openbookqa": load_openbookqa,
    "gsm8k": load_gsm8k,
    "truthfulqa_mc": load_truthfulqa_mc,
    "simpleqa": load_simpleqa,
    "shopping_mc": load_shopping_mc,
}


def load_benchmark(name: str, limit: int | None = None, seed: int = 0) -> list[dict[str, Any]]:
    if name not in LOADERS:
        raise KeyError(f"Unknown benchmark {name}; choose from {list(LOADERS)}")
    if limit is None:
        limit = DEFAULT_LIMITS.get(name)
    cache = Path(f"data/{name}_slice.json")
    if cache.exists():
        rows = json.loads(cache.read_text(encoding="utf-8"))
        # If cache matches requested limit, reuse; else reload.
        if limit is None or len(rows) == limit:
            # ensure idx contiguous
            for i, r in enumerate(rows):
                r["idx"] = i
            return rows
    return LOADERS[name](limit=limit, seed=seed)


def cache_benchmark(name: str, out_path: str | Path, limit: int | None = None, seed: int = 0) -> Path:
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = load_benchmark(name, limit=limit, seed=seed)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    return path
