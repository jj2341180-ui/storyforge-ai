"""
Offline Story Engine.

Generates ORIGINAL short-film scripts from structured genre packs - no external API,
no copyrighted characters. Every run combines randomized beats, names and motifs,
and the user can edit every word before rendering.
"""
from __future__ import annotations

import random
import uuid
from typing import Any

from .config import NARRATION_WPM

GENRES: dict[str, dict[str, Any]] = {
    "fantasy": {
        "label": "Fantasy & magical kingdoms",
        "titles": ["The {adj} Kingdom", "Ashes of {place}", "The {noun} of {place}", "Beyond the {adj} Gate"],
        "places": ["Aelmoor", "the Sunken Spire", "Vaeloria", "the Ember Marches", "Thornhaven"],
        "adjectives": ["Silver", "Forgotten", "Hollow", "Crimson", "Dreaming"],
        "nouns": ["Crown", "Pact", "Lantern", "Throne", "Oath"],
        "settings": [
            "a ruined dragon kingdom under a blackened moon",
            "a floating city held together by living vines",
            "an enchanted forest where rivers flow upward",
            "a marble citadel buried beneath the desert sand",
        ],
        "inciting": [
            "an ancient seal cracks open and cold light pours into the sky",
            "a dying dragon presses a glowing scale into {prot}'s hands",
            "the kingdom's eternal flame begins to turn black",
            "a masked stranger arrives with a map written in starlight",
        ],
        "obstacles": [
            "a bridge of mist that tests every traveler's memory",
            "a knight bound by an oath older than the kingdom",
            "a vault where the protagonist's own doubts take physical form",
            "a marketplace of stolen names, where speaking yours costs everything",
        ],
        "revelation": "the magic was never a gift to be claimed, but a responsibility to be carried",
        "motifs": ["falling ash", "distant burning towers", "runes glowing underfoot", "wind carrying whispers"],
        "antagonist": "the Hollow Sovereign",
    },
    "romance": {
        "label": "Romance & enemies-to-lovers",
        "titles": ["The {adj} Agreement", "Letters to {place}", "The {noun} Between Us", "Midnight at {place}"],
        "places": ["Willowmere", "the Old Lighthouse", "Ravenna", "the Harbor District"],
        "adjectives": ["Unexpected", "Secret", "Winter", "Borrowed"],
        "nouns": ["Promise", "Distance", "Recipe", "Last Dance"],
        "settings": [
            "a rain-soaked harbor town famous for its lighthouse",
            "two rival bookshops separated by a single narrow street",
            "a winter festival in a mountain village",
            "a vineyard during the final harvest of the decade",
        ],
        "inciting": [
            "{prot} is forced to share a workspace with the one person they cannot stand",
            "a misdelivered letter reveals a secret admirer",
            "a storm traps the two rivals overnight in an old lighthouse",
            "a family feud puts the family businesses on the brink of ruin",
        ],
        "obstacles": [
            "a public argument neither of them can take back",
            "a job offer in another country that must be answered by morning",
            "a long-buried family secret that explains everything",
            "a promise made to someone else years ago",
        ],
        "revelation": "the person they thought was their opposite was the one who truly saw them",
        "motifs": ["rain on windows", "paper lanterns", "steam rising from coffee cups", "handwritten notes"],
        "antagonist": "old pride",
    },
    "horror": {
        "label": "Horror & supernatural suspense",
        "titles": ["The {adj} House", "Whispers in {place}", "The {noun} That Wakes at Night", "Below {place}"],
        "places": ["Blackpine", "the Hollow", "Ashford Manor", "the Ninth Floor"],
        "adjectives": ["Empty", "Watching", "Silent", "Cold"],
        "nouns": ["Door", "Recording", "Portrait", "Visitor"],
        "settings": [
            "an isolated boarding house where the lights flicker at 3 a.m.",
            "a village that does not appear on any modern map",
            "an abandoned hospital converted into apartments",
            "a farmhouse surrounded by endless cornfields",
        ],
        "inciting": [
            "{prot} finds a locked room that appears in a different place each night",
            "every mirror in the house begins showing a room that does not exist",
            "a voice on an old recording knows {prot}'s name",
            "the townspeople politely refuse to speak about what happens after dark",
        ],
        "obstacles": [
            "a phone line that only receives calls from the house itself",
            "a photograph in which a figure stands closer each morning",
            "a neighbor who insists they have spoken for years, though they only just met",
            "a basement door that reappears even after being nailed shut",
        ],
        "revelation": "the haunting was a warning, and the living were never the prisoners",
        "motifs": ["flickering bulbs", "slow footsteps overhead", "fog against glass", "a music box winding itself"],
        "antagonist": "the thing that wears the house's silence",
    },
    "mystery": {
        "label": "Mystery & thriller",
        "titles": ["The {adj} Witness", "The {place} Affair", "The {noun} at Midnight", "Signals from {place}"],
        "places": ["Cardwell", "the Meridian Hotel", "North Quay", "the Glass Museum"],
        "adjectives": ["Vanishing", "Quiet", "Last", "Unreliable"],
        "nouns": ["Alibi", "Cipher", "Passenger", "Confession"],
        "settings": [
            "a grand hotel sealed for the winter storm",
            "a coastal town the night before a decisive election",
            "a night train crossing the mountains",
            "a tech campus where a founder has disappeared",
        ],
        "inciting": [
            "{prot} receives a confession meant for someone else",
            "a key witness vanishes from a locked interview room",
            "a dead man's watch arrives in the mail, still ticking",
            "a single frame of security footage has been deliberately erased",
        ],
        "obstacles": [
            "a witness whose story changes with every telling",
            "a benefactor who owns half the town's secrets",
            "a cipher hidden in a routine radio broadcast",
            "an ally found standing over the evidence they were meant to protect",
        ],
        "revelation": "the crime was hiding inside the one story everyone accepted without question",
        "motifs": ["neon reflections in rain", "steam from manholes", "redacted files", "train lights in fog"],
        "antagonist": "a conspiracy wearing a friendly face",
    },
    "adventure": {
        "label": "Adventure & action",
        "titles": ["The {adj} Expedition", "Escape from {place}", "The {noun} of Storms", "Race to {place}"],
        "places": ["Kharok", "the Iron Delta", "the Skyroad", "Zoravan"],
        "adjectives": ["Last", "Forgotten", "Bold", "Thunderbound"],
        "nouns": ["Compass", "Heist", "Crossing", "Relic"],
        "settings": [
            "a desert crossed by buried rails and sandstorm corridors",
            "an archipelago where maps are forbidden",
            "a vertical city built into a canyon wall",
            "a frozen route once used by smugglers",
        ],
        "inciting": [
            "{prot} inherits a compass that points at something instead of north",
            "a routine courier job turns into a chase across three districts",
            "an airship goes down carrying a cargo everyone wants buried",
            "a rival explorer steals the only map and leaves a fake behind",
        ],
        "obstacles": [
            "a collapsing rope bridge over a canyon",
            "a guarded gate with a price that cannot be paid in money",
            "a sandstorm that erases every landmark",
            "a betrayal at the moment the relic is within reach",
        ],
        "revelation": "the treasure was the journey's proof that ordinary people can choose courage",
        "motifs": ["wind-whipped banners", "sparks off metal", "distant thunder", "maps marked in red ink"],
        "antagonist": "a mercenary crew called the Iron Vow",
    },
    "drama": {
        "label": "Emotional drama",
        "titles": ["The {adj} Year", "After {place}", "The {noun} We Kept", "Sundays at {place}"],
        "places": ["Maple Street", "the Riverside Diner", "Bramblewood", "the Old Piano Hall"],
        "adjectives": ["Quiet", "Long", "Unfinished", "Tender"],
        "nouns": ["Letter", "Song", "Promise", "Photograph"],
        "settings": [
            "a family home being packed up after decades of memories",
            "a small-town diner that closes its doors for the last time",
            "a hospital ward where strangers become confidants",
            "a music school on the brink of closing",
        ],
        "inciting": [
            "{prot} finds a box of unsent letters in a late parent's closet",
            "a phone call brings a fractured family back under one roof",
            "an old piano is scheduled for demolition by week's end",
            "a stranger returns a lost wallet with a note inside",
        ],
        "obstacles": [
            "a conversation the family has avoided for fifteen years",
            "a sacrifice demanded by a promise made long ago",
            "the temptation to leave town and never look back",
            "a confession that could heal or finally break the family",
        ],
        "revelation": "hearing each other was harder than any hardship they had survived alone",
        "motifs": ["golden afternoon light", "dust motes in attics", "a kettle whistling", "faded photographs"],
        "antagonist": "years of unspoken words",
    },
    "children": {
        "label": "Children's stories",
        "titles": ["The {adj} Little {noun}", "{prot}'s Big Day in {place}", "The {noun} Who Couldn't Sleep", "Hello, {place}!"],
        "places": ["Meadowbrook", "the Cloud Orchard", "Buttonwood", "the Starry Pond"],
        "adjectives": ["Brave", "Curious", "Sleepy", "Friendly"],
        "nouns": ["Fox", "Lantern", "Cloud", "Mailbox"],
        "settings": [
            "a sunny meadow where the flowers ring like tiny bells",
            "a treehouse village connected by rope bridges",
            "a pond that reflects a different sky every night",
            "a bakery run entirely by forest animals",
        ],
        "inciting": [
            "{prot} discovers the moon has misplaced one of its stars",
            "a new neighbor arrives who speaks only in colors",
            "the annual lantern festival is one lantern short",
            "a tiny dragon gets lost on its first day of flying school",
        ],
        "obstacles": [
            "a grumpy troll who is actually just very lonely",
            "a river crossing with no bridge and only one very small boat",
            "a puzzle with three silly clues and one tasty answer",
            "a fear of the dark that must be gently outsmarted",
        ],
        "revelation": "asking for help is the bravest thing a friend can do",
        "motifs": ["butterflies", "warm lantern glow", "dandelion seeds", "giggling brooks"],
        "antagonist": "a small misunderstanding",
    },
    "shortfilm": {
        "label": "Original short films",
        "titles": ["The {adj} Minute", "{place}, 11:47", "The {noun} Reel", "Static over {place}"],
        "places": ["the East Platform", "Lumen Bay", "the Foundry", "Hallway 7"],
        "adjectives": ["Final", "Held", "Breaking", "Open"],
        "nouns": ["Audition", "Night Shift", "Return", "Signal"],
        "settings": [
            "a 24-hour laundromat on a rainy Tuesday",
            "the last carriage of an overnight train",
            "a radio station broadcasting its final show",
            "a rooftop where two strangers take the same break each night",
        ],
        "inciting": [
            "{prot} finds a roll of undeveloped film in a donated coat",
            "two strangers keep arriving at the same rooftop at midnight",
            "a final radio broadcast receives one impossible caller",
            "a night-shift worker notices the clock outside has stopped",
        ],
        "obstacles": [
            "a choice between truth and the only safe option",
            "a deadline measured in minutes, not days",
            "a confession rehearsed a hundred times and never spoken",
            "one last chance that depends entirely on trust",
        ],
        "revelation": "a single honest moment can reroute an entire life",
        "motifs": ["vending-machine light", "wet asphalt", "analog dials", "distant city hum"],
        "antagonist": "the weight of an unmade choice",
    },
}

FIRST_NAMES = ["Maren", "Kael", "Soraya", "Dev", "Ilyana", "Theo", "Noor", "Cass", "Ren", "Amara",
               "Jules", "Oren", "Lina", "Bash", "Wren", "Idris", "Esme", "Tavi", "Nadia", "Fenn"]
COMPANIONS = ["a quick-witted engineer", "a quiet herbalist", "an elderly mapmaker with a secret",
              "a runaway apprentice", "a talking raven with excellent manners"]
DIALOGUE = [
    ("{prot}", "Tell me that again, slowly."),
    ("{ally}", "You knew, and you said nothing?"),
    ("{prot}", "I didn't say nothing. I said it quietly, to myself."),
    ("{ally}", "We're running out of road."),
    ("{prot}", "Then we stop running."),
    ("{ally}", "That is either the bravest or the stupidest plan I've ever heard."),
    ("{prot}", "Why not both?"),
    ("{ally}", "Do you trust me?"),
    ("{prot}", "With the one thing I can't afford to lose."),
]
ENDINGS = {
    "happy": "By dawn, what was broken has begun to mend. {prot} walks home lighter, surrounded by the people who chose to stay, as {motif} settles gently over the world.",
    "tragic": "In the end, the price is paid in full. {prot} stands alone with the victory no one else lived to see, while {motif} marks the silence that follows.",
    "mysterious": "Then the last light changes shape, and a new question opens where an answer should have been. Some doors, {prot} realizes, are only beginning to unlock.",
    "open": "{prot} makes the choice, steps forward, and does not look back. Whether it was the right one, the road ahead has not yet decided.",
}
TONE_ADJ = {
    "dark": ["cold", "shadowed", "unforgiving"],
    "dreamy": ["soft", "hazy", "luminous"],
    "epic": ["vast", "thunderous", "monumental"],
    "cozy": ["warm", "gentle", "familiar"],
    "tense": ["narrow", "breathless", "sharp"],
    "whimsical": ["playful", "curious", "delightful"],
    "melancholic": ["fading", "quiet", "bittersweet"],
}
CAMERA_STYLES = ["slow cinematic dolly", "handheld intimacy", "sweeping aerial drift", "locked-off painterly frames", "steady tracking shots"]
LIGHTING = ["moonlit chiaroscuro", "golden-hour glow", "cold blue twilight", "flickering practical lantern light", "overcast soft light"]
PALETTES = ["desaturated teal and amber", "deep indigo with silver highlights", "warm ember orange and charcoal",
            "muted forest greens", "monochrome with a single red accent"]


def _pov_text(pov: str, prot: str, sentence: str) -> str:
    """Lightweight first/third person framing."""
    if pov == "first":
        return sentence.replace(f"{prot} ", "I ").replace(f"{prot},", "I,").replace(f"{prot}.", "I.")
    return sentence


def generate_story(settings: dict[str, Any], seed: int | None = None) -> dict[str, Any]:
    rng = random.Random(seed if seed is not None else random.randint(0, 10_000_000))
    genre_key = settings.get("category", "fantasy")
    pack = GENRES.get(genre_key, GENRES["fantasy"])
    tone = settings.get("tone", "epic")
    pov = settings.get("pov", "third")
    n_scenes = max(3, min(int(settings.get("sceneCount", 5)), 10))
    ending_type = settings.get("ending", "open")
    audience = settings.get("audience", "General")
    children_mode = genre_key == "children" or audience == "Young children"

    prot = rng.choice(FIRST_NAMES)
    ally = rng.choice(COMPANIONS)
    place = rng.choice(pack["places"])
    motif = rng.choice(pack["motifs"])
    adj = rng.choice(pack["adjectives"])
    noun = rng.choice(pack["nouns"])
    title = rng.choice(pack["titles"]).format(adj=adj, place=place, noun=noun, prot=prot)

    style = {
        "location": rng.choice(pack["settings"]),
        "lighting": rng.choice(LIGHTING),
        "palette": rng.choice(PALETTES),
        "camera": rng.choice(CAMERA_STYLES),
        "effects": f"{rng.choice(TONE_ADJ.get(tone, TONE_ADJ['epic']))} atmosphere, {motif}, subtle film grain",
    }

    hook = (
        f"In {style['location']}, {motif} fills the air the night everything changes for {prot}. "
        f"None of the old stories mention someone like {prot} - which is exactly why the story begins now."
    )
    inciting = rng.choice(pack["inciting"]).format(prot=prot)
    article = "an" if tone[:1].lower() in "aeiou" else "a"
    logline = (
        f"{'A gentle tale' if children_mode else article.capitalize() + ' ' + tone + ' story'} "
        f"set in {style['location']}. "
        f"When {inciting}, {prot} must face {pack['antagonist']} and discover that {pack['revelation']}."
    )

    # ---- build scenes: hook -> rising obstacles -> climax -> ending ----
    # Fixed beats (hook, climax, ending) take 3 slots; the rest are obstacle/trial scenes.
    n_obstacles = max(0, n_scenes - 3)
    obstacles = rng.sample(pack["obstacles"], k=min(n_obstacles, len(pack["obstacles"])))
    while len(obstacles) < n_obstacles:
        obstacles.append(rng.choice(pack["obstacles"]))
    scenes: list[dict[str, Any]] = []
    dialogue_pool = rng.sample(DIALOGUE, k=min(4, len(DIALOGUE)))

    display_place = place[:1].upper() + place[1:] if place.startswith("the ") else place

    # Scene 1 - opening hook
    scenes.append({
        "id": str(uuid.uuid4()),
        "heading": f"Scene 1 - {display_place}: The Night It Begins",
        "narration": _pov_text(pov, prot, hook + " " + inciting.capitalize() + "."),
        "dialogue": "",
        "visual_prompt": "",
        "notes": f"Opening hook. Establish {style['location']} and {motif}.",
    })

    # Middle scenes - rising action
    for i, obstacle in enumerate(obstacles, start=2):
        beat = (
            f"With no map left to trust, {prot} confronts {obstacle}. {ally.title()} stands nearby, "
            f"watching carefully, while {motif} fills the space around them."
        )
        d_lines = []
        if dialogue_pool:
            who, line = dialogue_pool.pop()
            d_lines.append(f"{who.format(prot=prot, ally='Companion').split(':')[0] if False else ''}{who.format(prot=prot, ally=ally.title())}: {line.format(prot=prot, ally=ally.title())}")
            if dialogue_pool and i % 2 == 0:
                who2, line2 = dialogue_pool.pop()
                d_lines.append(f"{who2.format(prot=prot, ally=ally.title())}: {line2.format(prot=prot, ally=ally.title())}")
        scenes.append({
            "id": str(uuid.uuid4()),
            "heading": f"Scene {i} - Trial {i - 1}",
            "narration": _pov_text(pov, prot, beat),
            "dialogue": "\n".join(d_lines),
            "visual_prompt": "",
            "notes": f"Rising action; show, don't tell. Motif: {motif}.",
        })

    # Climax
    scenes.append({
        "id": str(uuid.uuid4()),
        "heading": f"Scene {len(scenes) + 1} - The Confrontation",
        "narration": _pov_text(
            pov, prot,
            f"Everything converges. Face to face with {pack['antagonist']}, {prot} finally understands: "
            f"{pack['revelation']}. The choice that remains belongs to no one else.",
        ),
        "dialogue": (f"{prot}: I'm not the person you expected.\n"
                     f"{'Companion' if pov == 'first' else ally.title()}: Good. They never were."),
        "visual_prompt": "",
        "notes": "Emotional and visual climax.",
    })

    # Ending
    scenes.append({
        "id": str(uuid.uuid4()),
        "heading": f"Scene {len(scenes) + 1} - What Remains",
        "narration": _pov_text(pov, prot, ENDINGS[ending_type].format(prot=prot, motif=motif)),
        "dialogue": "",
        "visual_prompt": "",
        "notes": f"{ending_type.title()} ending.",
    })

    # ---- characters ----
    characters = [{
        "id": str(uuid.uuid4()),
        "name": prot,
        "age_range": "19-28" if not children_mode else "8-12",
        "appearance": "expressive eyes, determined posture",
        "hair": "silver-streaked dark hair" if genre_key == "fantasy" else "unkempt chestnut hair",
        "eyes": "gray-green",
        "clothing": "practical layered travel clothing with one distinctive token",
        "personality": "curious, stubborn, quietly brave",
        "features": f"keeps a memento connected to {motif}",
        "ref_asset_id": None,
    }]
    if not children_mode:
        characters.append({
            "id": str(uuid.uuid4()),
            "name": ally.title(),
            "age_range": "30-55",
            "appearance": "weathered face, calm hands",
            "hair": "close-cropped graying hair",
            "eyes": "warm brown",
            "clothing": "well-worn functional garb with many pockets",
            "personality": "patient, wry, fiercely loyal",
            "features": "always carries the same worn satchel",
            "ref_asset_id": None,
        })

    # ---- visual prompts (consistency baked in from characters + style) ----
    char_desc = "; ".join(f"{c['name']}: {c['age_range']}, {c['hair']}, {c['eyes']} eyes, {c['clothing']}" for c in characters)
    for i, sc in enumerate(scenes):
        imagery = sc["heading"].split(" - ")[-1]
        sc["visual_prompt"] = (
            f"Cinematic {pack['label'].lower()} scene, {imagery}. {sc['narration'][:180]} "
            f"Style: {style['camera']}, {style['lighting']}, {style['palette']}, {style['effects']}. "
            f"Characters - keep consistent: {char_desc}. Widescreen film still, highly detailed, "
            f"no text, no watermark, no logos."
        )

    # ---- duration estimate ----
    words = sum(len((s["narration"] + " " + s["dialogue"]).split()) for s in scenes)
    est_seconds = round(words / NARRATION_WPM * 60)
    target_seconds = int(float(settings.get("length", 3)) * 60)
    mismatch = None
    if abs(est_seconds - target_seconds) > max(20, target_seconds * 0.25):
        mismatch = (
            f"Narration estimates ~{est_seconds // 60}m {est_seconds % 60}s but target is "
            f"{target_seconds // 60}m {target_seconds % 60}s. Adjust scene count or script length before rendering."
        )

    return {
        "title": title,
        "logline": logline,
        "scenes": scenes,
        "characters": characters,
        "style": style,
        "narration_words": words,
        "estimated_seconds": est_seconds,
        "duration_warning": mismatch,
        "originality": (
            "Generated locally from randomized genre components. Names, places and plots are invented; "
            "no existing books, films or copyrighted characters are used."
        ),
        "seed": rng.randint(0, 10_000_000),
    }


def split_script(raw: str) -> list[dict[str, Any]]:
    """Split a user-pasted script into scenes on 'Scene' headings or blank-line paragraphs."""
    blocks = [b.strip() for b in raw.replace("\r\n", "\n").split("\n\n") if b.strip()]
    scenes: list[dict[str, Any]] = []
    idx = 1
    for block in blocks:
        heading = f"Scene {idx}"
        body = block
        if block.lower().startswith("scene") and "\n" in block:
            heading, body = block.split("\n", 1)
        dialogue_lines = [l for l in body.split("\n") if ":" in l and len(l.split(":")[0].split()) <= 4]
        narration = "\n".join(l for l in body.split("\n") if l not in dialogue_lines)
        scenes.append({
            "id": str(uuid.uuid4()),
            "heading": heading.strip()[:120],
            "narration": narration.strip(),
            "dialogue": "\n".join(dialogue_lines).strip(),
            "visual_prompt": "",
            "notes": "",
        })
        idx += 1
    return scenes
