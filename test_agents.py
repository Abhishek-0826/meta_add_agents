from app.agents.research_agent import run_research_agent
from app.agents.strategy_agent import run_strategy_agent
from app.agents.copywriter_agent import run_copywriter_agent
from app.agents.translation_agent import (
    run_translation_agent,
    should_translate,
)
from app.agents.creative_agent import run_creative_agent
from app.agents.image_agent import run_image_agent
from app.agents.compliance_agent import run_compliance_agent
from app.agents.assembly_agent import run_assembly_agent
from app.agents.budget_guard import run_budget_guard


# ============================================================
# GET CAMPAIGN BRIEF FROM USER
# ============================================================

def get_user_brief():
    print("\n" + "=" * 60)
    print("ADPILOT - CAMPAIGN BRIEF")
    print("=" * 60)

    print("\nPlease enter the campaign details.\n")

    product = input("Product / Service: ").strip()

    selling_points = input(
        "Selling points: "
    ).strip()

    offer = input(
        "Offer (optional): "
    ).strip()

    landing_destination = input(
        "Landing destination URL: "
    ).strip()

    platform = input(
        "Platform [instagram]: "
    ).strip() or "instagram"

    placement = input(
        "Placement [auto]: "
    ).strip() or "auto"

    countries_input = input(
        "Countries [IN]: "
    ).strip() or "IN"

    languages_input = input(
        "Languages [en]: "
    ).strip() or "en"

    age_range = input(
        "Age range [25-40]: "
    ).strip() or "25-40"

    gender = input(
        "Gender [female_leaning]: "
    ).strip() or "female_leaning"

    audience_description = input(
        "Audience description: "
    ).strip()

    exclusions = input(
        "Audience exclusions (optional): "
    ).strip()

    objective = input(
        "Campaign objective [sales]: "
    ).strip() or "sales"

    format_type = input(
        "Creative format [single_image]: "
    ).strip() or "single_image"

    creative_choice = input(
        "Creative choice [generate/upload]: "
    ).strip().lower() or "generate"

    uploaded_asset_urls = []

    if creative_choice == "upload":

        print(
            "\nEnter uploaded image URLs separated by commas."
        )

        uploaded_input = input(
            "Image URLs: "
        ).strip()

        if uploaded_input:

            uploaded_asset_urls = [
                url.strip()
                for url in uploaded_input.split(",")
                if url.strip()
            ]

    budget_type = input(
        "Budget type [daily]: "
    ).strip() or "daily"

    budget_amount_input = input(
        "Budget amount [500]: "
    ).strip() or "500"

    try:
        budget_amount = float(budget_amount_input)
    except ValueError:
        print(
            "\nInvalid budget amount. Using 500."
        )
        budget_amount = 500

    brief = {
        "product": product,

        "selling_points": selling_points,

        "offer": offer,

        "landing_destination": landing_destination,

        "platform": platform,

        "placement": placement,

        "countries": [
            country.strip()
            for country in countries_input.split(",")
            if country.strip()
        ],

        "languages": [
            language.strip()
            for language in languages_input.split(",")
            if language.strip()
        ],

        "age_range": age_range,

        "gender": gender,

        "audience_description": audience_description,

        "exclusions": exclusions or None,

        "objective": objective,

        "format": format_type,

        "creative_choice": creative_choice,

        "uploaded_asset_urls": uploaded_asset_urls,

        "budget_type": budget_type,

        "budget_amount": budget_amount,
    }

    return brief


# ============================================================
# CREATE INITIAL PIPELINE STATE
# ============================================================

def create_initial_state(brief):

    return {
        "job_id": "test-job-001",

        "client_id": "test-client-001",

        # USER BRIEF
        "brief": brief,

        # BRAND INFORMATION
        "brand_voice": "warm, cozy, a little playful",

        "default_language": (
            brief.get("languages", ["en"])[0]
        ),

        # GUARD RAILS
        "guard_rails": {
            "max_daily_budget": 5000,
            "max_lifetime_budget": 50000,
            "blocked_keywords": [],
        },

        # AGENT OUTPUTS
        "research": {},

        "strategy": {},

        "copy_variants": {},

        "translated_copy": {},

        "creative": {},

        "image": {},

        "compliance": {},

        "assembled_payload": {},

        "budget_guard": {},

        # PIPELINE CONTROL
        "current_node": "start",

        "halted": False,

        "halt_reason": "",

        "errors": [],
    }


# ============================================================
# AGENT TEST FUNCTION
# ============================================================

def run_test(
    agent_name,
    agent_function,
    state,
):

    print("\n" + "=" * 50)
    print(f"Running: {agent_name}")
    print("=" * 50)

    try:

        state = agent_function(state)

        print(
            "halted:",
            state.get("halted", False),
        )

        if state.get("halted"):

            print(
                "halt_reason:"
            )

            print(
                state.get("halt_reason")
            )

        print("\noutput:")

        if agent_name == "RESEARCH AGENT":

            print(
                state.get("research")
            )

        elif agent_name == "STRATEGY AGENT":

            print(
                state.get("strategy")
            )

        elif agent_name == "COPYWRITER AGENT":

            print(
                state.get("copy_variants")
            )

        elif agent_name == "TRANSLATION AGENT":

            print(
                state.get("translated_copy")
            )

        elif agent_name == "CREATIVE AGENT":

            print(
                state.get("creative")
            )

        elif agent_name == "IMAGE AGENT":

            print(
                state.get("image")
            )

        elif agent_name == "COMPLIANCE AGENT":

            print(
                state.get("compliance")
            )

        elif agent_name == "ASSEMBLY AGENT":

            print(
                state.get("assembled_payload")
            )

        elif agent_name == "BUDGET GUARD":

            print(
                state.get("budget_guard")
            )

        return state

    except Exception as e:

        print("\nERROR:")

        print(e)

        state["halted"] = True

        state["halt_reason"] = str(e)

        state.setdefault(
            "errors",
            []
        ).append(str(e))

        return state


# ============================================================
# MAIN
# ============================================================

def main():

    # --------------------------------------------------------
    # 1. GET BRIEF FROM USER
    # --------------------------------------------------------

    brief = get_user_brief()

    print("\n" + "=" * 60)
    print("CAMPAIGN BRIEF RECEIVED")
    print("=" * 60)

    print(brief)

    # --------------------------------------------------------
    # 2. CREATE INITIAL STATE
    # --------------------------------------------------------

    fake_state = create_initial_state(
        brief
    )

    # ========================================================
    # 3. RESEARCH
    # ========================================================

    fake_state = run_test(
        "RESEARCH AGENT",
        run_research_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 4. STRATEGY
    # ========================================================

    fake_state = run_test(
        "STRATEGY AGENT",
        run_strategy_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 5. COPYWRITER
    # ========================================================

    fake_state = run_test(
        "COPYWRITER AGENT",
        run_copywriter_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 6. TRANSLATION
    # ========================================================

    if should_translate(fake_state):

        fake_state = run_test(
            "TRANSLATION AGENT",
            run_translation_agent,
            fake_state,
        )

        if fake_state.get("halted"):
            return

    else:

        print("\n" + "=" * 50)
        print("TRANSLATION AGENT")
        print("=" * 50)

        print(
            "Translation not required."
        )

        fake_state["translated_copy"] = None

    # ========================================================
    # 7. CREATIVE
    # ========================================================

    fake_state = run_test(
        "CREATIVE AGENT",
        run_creative_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 8. IMAGE
    # ========================================================

    fake_state = run_test(
        "IMAGE AGENT",
        run_image_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 9. COMPLIANCE
    # ========================================================

    fake_state = run_test(
        "COMPLIANCE AGENT",
        run_compliance_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 10. ASSEMBLY
    # ========================================================

    fake_state = run_test(
        "ASSEMBLY AGENT",
        run_assembly_agent,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # 11. BUDGET GUARD
    # ========================================================

    fake_state = run_test(
        "BUDGET GUARD",
        run_budget_guard,
        fake_state,
    )

    if fake_state.get("halted"):
        return

    # ========================================================
    # FINAL RESULT
    # ========================================================

    print("\n")

    print("=" * 60)
    print("PIPELINE COMPLETED")
    print("=" * 60)

    print(
        "Halted:",
        fake_state.get("halted"),
    )

    print(
        "Current node:",
        fake_state.get("current_node"),
    )

    # ========================================================
    # IMAGE RESULT
    # ========================================================

    print("\nImage result:")

    image_result = fake_state.get(
        "image",
        {},
    )

    print(image_result)

    if image_result.get("generated"):

        print(
            "\nIMAGE GENERATED SUCCESSFULLY"
        )

        print(
            "Local file:",
            image_result.get("path"),
        )

        print(
            "Image URL:",
            image_result.get("image_url"),
        )

    else:

        print(
            "\nNo new AI image was generated."
        )

    # ========================================================
    # FINAL STATE
    # ========================================================

    print("\n" + "=" * 60)
    print("FINAL STATE")
    print("=" * 60)

    print(fake_state)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()