
from protocols import classify_complaint, estimate_priority

test_cases = [
    "Minor pothole on a quiet street",
    "Deep pothole causing accidents on the road",
    "Garbage has been uncollected for several days",
    "Broken streetlight near a school",
    "A live wire is hanging over a busy road",
    "There are no live wires or electrical hazards here",
    "No accidents have been reported near this pothole",
    "Water pipe has burst and flooded the street",
    "No electricity in our area for two days",
    "Exposed electrical wire is sparking near a hospital",
    "Garbage collection is regular and there is no garbage problem",
    "Garbage collection is regular and there is no garbage problem",
    "There is no garbage collection in our area for five days",
    "The exposed electrical wire is sparking near a hospital",
]

for complaint in test_cases:
    category = classify_complaint(complaint)
    priority = estimate_priority(complaint)

    print(f"\nComplaint: {complaint}")
    print(f"Category: {category}")
    print(f"Priority: {priority}/100")
edge_cases = [
    "There is a pothole near the school",
    "There is no pothole on this street",
    "A live wire is hanging near a hospital",
    "Garbage has not been collected for seven days",
]

for complaint in edge_cases:
    print(f"\nComplaint: {complaint}")
    print(f"Category: {classify_complaint(complaint)}")
    print(f"Priority: {estimate_priority(complaint)}/100")    
