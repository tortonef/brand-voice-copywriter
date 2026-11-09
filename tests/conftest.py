import pytest

from brand_voice.config import load_config
from brand_voice.data import load_brands, load_lexicon, load_products, load_seeded


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def products(cfg):
    return load_products(cfg["paths"]["products"], cfg["paths"]["schema"])


@pytest.fixture(scope="session")
def brands(cfg):
    return load_brands(cfg["paths"]["brands"])


@pytest.fixture(scope="session")
def lexicon(cfg):
    return load_lexicon(cfg["paths"]["claims"])


@pytest.fixture(scope="session")
def seeded(cfg):
    return load_seeded(cfg["paths"]["seeded"])


@pytest.fixture
def good_copy():
    """A compliant English Maison Lumen text for ML-0001 (cashmere sweater)."""
    return {
        "title": "Cashmere Crewneck in Camel",
        "description": (
            "A crewneck sweater in fine-gauge cashmere, in a warm camel shade. The regular fit falls "
            "straight to the hip, and the ribbed cuffs and hem keep a clean line at the wrist and waist. "
            "Wear it on its own with tailored trousers at the office, or over a shirt at the weekend. "
            "Through autumn and winter it pairs with grey, navy and ivory pieces, and it layers easily "
            "under a coat on the colder days of the season."
        ),
        "bullets": [
            "Fine-gauge cashmere knit",
            "Regular fit, crew neckline",
            "Ribbed cuffs and hem",
        ],
    }
