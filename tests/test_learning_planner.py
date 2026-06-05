from src.learning.service import MaterialLearningPlanner
from src.materials.entities import MaterialType
from src.materials.service import MaterialCollection


def test_learning_planner_accepts_all_material_types_through_one_boundary():
    collection = MaterialCollection()
    collection.add_text("manual note about a market signal")
    collection.add_external_ref(MaterialType.SCREENSHOT, "image:1", title="Screenshot")
    collection.add_external_ref(MaterialType.DOCUMENT, "file:1", title="Report")
    collection.add_external_ref(MaterialType.MEDIA, "media:1", title="Interview")
    collection.add_link("https://example.com/research")

    plan = MaterialLearningPlanner().create_plan(collection.ready_for_learning())

    assert [segment.material_type for segment in plan.segments] == [
        MaterialType.TEXT,
        MaterialType.SCREENSHOT,
        MaterialType.DOCUMENT,
        MaterialType.MEDIA,
        MaterialType.LINK,
    ]
    assert len(plan.selected_segments) == 5


def test_learning_planner_assigns_type_specific_purpose():
    collection = MaterialCollection()
    collection.add_link("https://example.com/research")

    plan = MaterialLearningPlanner().create_plan(collection.ready_for_learning())

    assert plan.segments[0].purpose == "Resolve the link into a processable material before learning."


def test_learning_plan_summary_reports_material_count():
    collection = MaterialCollection()
    collection.add_text("one")
    collection.add_text("two")

    plan = MaterialLearningPlanner().create_plan(collection.ready_for_learning())

    assert plan.summary == "2 material(s) ready for learning."
