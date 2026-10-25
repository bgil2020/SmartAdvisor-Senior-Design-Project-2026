
BEGIN;

-- Stop if any demo course ID belongs to unexpected data.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM public.courses
        WHERE course_id IN (
            'DEMO_COP301',
            'DEMO_COP302',
            'DEMO_COP303'
        )
        AND (
            department IS DISTINCT FROM 'DEMO'
            OR title NOT IN (
                'Demo Programming',
                'Demo Data Structures',
                'Demo Databases'
            )
        )
    )
    OR EXISTS (
        SELECT 1
        FROM public.sections
        WHERE crn IN ('990001', '990002', '990003')
        AND (
            (crn = '990001' AND course_id IS DISTINCT FROM 'DEMO_COP301')
            OR (crn = '990002' AND course_id IS DISTINCT FROM 'DEMO_COP302')
            OR (crn = '990003' AND course_id IS DISTINCT FROM 'DEMO_COP303')
        )
    )
    THEN
        RAISE EXCEPTION
            'Reset cancelled: conflicting demo records detected.';
    END IF;
END
$$;

-- Remove only the three identified demo sections.
DELETE FROM public.sections
WHERE (crn = '990001' AND course_id = 'DEMO_COP301')
   OR (crn = '990002' AND course_id = 'DEMO_COP302')
   OR (crn = '990003' AND course_id = 'DEMO_COP303');

-- Remove demo risk rules referencing these courses.
DELETE FROM public.risk_rules
WHERE course_id_1 IN (
    'DEMO_COP301', 'DEMO_COP302', 'DEMO_COP303'
)
AND course_id_2 IN (
    'DEMO_COP301', 'DEMO_COP302', 'DEMO_COP303'
);

-- Remove demo courses only when no sections or rules reference them.
DELETE FROM public.courses c
WHERE c.course_id IN (
    'DEMO_COP301',
    'DEMO_COP302',
    'DEMO_COP303'
)
AND NOT EXISTS (
    SELECT 1 FROM public.sections s
    WHERE s.course_id = c.course_id
)
AND NOT EXISTS (
    SELECT 1 FROM public.risk_rules r
    WHERE r.course_id_1 = c.course_id
       OR r.course_id_2 = c.course_id
);

COMMIT;
