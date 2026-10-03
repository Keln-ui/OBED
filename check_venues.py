import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
import django
django.setup()

from revision.models import Class as SchoolClass
from timetable.models import Venue, ClassTimetable, ClassTimetableEntry

print("=== CLASSES ===")
for c in SchoolClass.objects.all():
    print(f"  Class #{c.id}: {c.name}")

print("\n=== VENUES ===")
for v in Venue.objects.all():
    print(f"  Venue #{v.id}: {v.name}")

print("\n=== TIMETABLE VENUE MAPPING ===")
for ct in ClassTimetable.objects.all().order_by('id'):
    entry = ClassTimetableEntry.objects.filter(class_timetable=ct).first()
    venue_name = entry.venue.name if entry and entry.venue else "(no venue)"
    print(f"  Timetable #{ct.id}: {ct.class_group.name} -> Venue: {venue_name}")

print("\n=== IMPROVED VENUE MATCHING TEST ===")
abbreviation_map = {
    'e': 'east', 'w': 'west', 'n': 'north', 's': 'south',
}

for c in SchoolClass.objects.all():
    class_name_lower = c.name.lower()
    parts = class_name_lower.split()
    
    # Build search keys: try expanded abbreviation first, then original
    search_keys = [class_name_lower]
    
    # If last part is an abbreviation, add expanded version
    if parts and parts[-1] in abbreviation_map:
        expanded = ' '.join(parts[:-1]) + ' ' + abbreviation_map[parts[-1]]
        search_keys.insert(0, expanded)  # Try expanded first
    
    matched = None
    matched_score = 999
    
    for v in Venue.objects.all():
        vl = v.name.lower()
        for key in search_keys:
            if key == vl:
                # Exact match = best
                if matched_score > 0:
                    matched = v.name
                    matched_score = 0
            elif key in vl:
                # Partial match
                if matched_score > 1:
                    matched = v.name
                    matched_score = 1
    
    if matched:
        print(f"  {c.name} -> {matched} (score={matched_score})")
    else:
        print(f"  {c.name} -> NO MATCH (will use class name as venue text)")