
BEGIN;

-- Verify that existing demo IDs belong to the expected records.
-- Stop before inserting anything if a conflicting record is found.

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.courses
        WHERE course_id = 'DEMO_COP301'
          AND (title, department, credit_hours)
              IS DISTINCT FROM ('Demo Programming', 'DEMO', 3.00)
    )
    OR EXISTS (
        SELECT 1
        FROM public.courses
        WHERE course_id = 'DEMO_COP302'
          AND (title, department, credit_hours)
              IS DISTINCT FROM ('Demo Data Structures', 'DEMO', 3.00)
    )
    OR EXISTS (
        SELECT 1
        FROM public.courses
        WHERE course_id = 'DEMO_COP303'
          AND (title, department, credit_hours)
              IS DISTINCT FROM ('Demo Databases', 'DEMO', 3.00)
    )
    OR EXISTS (
        SELECT 1
        FROM public.sections
        WHERE crn IN ('990001', '990002', '990003')
          AND (
              (crn = '990001' AND course_id <> 'DEMO_COP301')
              OR (crn = '990002' AND course_id <> 'DEMO_COP302')
              OR (crn = '990003' AND course_id <> 'DEMO_COP303')
          )
    ) THEN
        RAISE EXCEPTION
            'Seed cancelled: conflicting demo IDs detected.';
    END IF;
END
$$;

INSERT INTO public.courses
    (course_id, title, department, credit_hours)
VALUES
    ('DEMO_COP301', 'Demo Programming', 'DEMO', 3.00),
    ('DEMO_COP302', 'Demo Data Structures', 'DEMO', 3.00),
    ('DEMO_COP303', 'Demo Databases', 'DEMO', 3.00)
ON CONFLICT (course_id) DO NOTHING;

INSERT INTO public.sections
    (crn, course_id, term, section_number, campus,
     days, start_time, end_time, method,
     seats_remaining, enrollment_status)
VALUES
    ('990001', 'DEMO_COP301', 202701, '001', 'Boca Raton',
     'MWF', '09:00', '09:50', 'In-Person', 20, 'Open'),
    ('990002', 'DEMO_COP302', 202701, '001', 'Boca Raton',
     'MWF', '09:30', '10:20', 'In-Person', 15, 'Open'),
    ('990003', 'DEMO_COP303', 202701, '001', 'Online',
     NULL, NULL, NULL, 'Online', 30, 'Open')
ON CONFLICT (crn) DO NOTHING;

COMMIT;
