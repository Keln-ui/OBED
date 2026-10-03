import os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'word_converter.settings')
import django
django.setup()

from timetable.models import ClassTimetable, ClassTimetableEntry, TeacherAllocation
from collections import Counter

day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']

for ct in ClassTimetable.objects.all().order_by('id'):
    count = ClassTimetableEntry.objects.filter(class_timetable=ct).count()
    subjects_list = ClassTimetableEntry.objects.filter(class_timetable=ct).values_list('subject_name', flat=True)
    
    print(f"\n=== Timetable #{ct.id}: {ct.class_group.name} ({ct.term} {ct.year}) ===")
    print(f"  Total entries: {count}")
    
    # Per-day breakdown
    all_day_subjects = []
    for day_id in range(5):
        day_entries = ClassTimetableEntry.objects.filter(class_timetable=ct, day=day_id)
        subs = [e.subject_name for e in day_entries]
        all_day_subjects.extend(subs)
        if subs:
            print(f"  {day_names[day_id]}: {', '.join(subs)}")
        else:
            print(f"  {day_names[day_id]}: (empty)")
    
    print(f"  Overall subjects: {', '.join(list(set(subjects_list)))}")
    
    # Show allocations for this class
    if ct.class_group:
        print(f"  Allocations:")
        for a in TeacherAllocation.objects.filter(class_group=ct.class_group):
            n = ClassTimetableEntry.objects.filter(class_timetable=ct, subject_name=a.subject.name).count()
            print(f"    {a.subject.name}: {a.weekly_lessons} allocated, {n} actual")
    print()