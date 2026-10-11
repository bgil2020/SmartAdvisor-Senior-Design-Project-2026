
CREATE TABLE IF NOT EXISTS public.courses (
    course_id VARCHAR(20) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    department VARCHAR(20),
    credit_hours DECIMAL(4,2) CHECK (credit_hours >= 0)
);

ALTER TABLE public.courses ENABLE ROW LEVEL SECURITY;


CREATE TABLE IF NOT EXISTS public.sections (
    crn VARCHAR(20) PRIMARY KEY,
    course_id VARCHAR(20) NOT NULL,
    term INTEGER NOT NULL,
    section_number VARCHAR(10) NOT NULL,
    campus VARCHAR(100),
    days VARCHAR(20),
    start_time TIME,
    end_time TIME,
    method VARCHAR(50),
    seats_remaining INTEGER CHECK (seats_remaining >= 0),
    enrollment_status VARCHAR(20),

    CONSTRAINT fk_course
        FOREIGN KEY (course_id)
        REFERENCES public.courses(course_id),

    CONSTRAINT valid_meeting_times
        CHECK (
            start_time IS NULL
            OR end_time IS NULL
            OR end_time > start_time
        )
);

ALTER TABLE public.sections ENABLE ROW LEVEL SECURITY;


CREATE TABLE IF NOT EXISTS public.risk_rules (
    risk_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    course_id_1 VARCHAR(20) NOT NULL,
    course_id_2 VARCHAR(20) NOT NULL,
    risk_category VARCHAR(100) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    explanation TEXT NOT NULL,
    recommended_action TEXT,

    CONSTRAINT fk_risk_course_1
        FOREIGN KEY (course_id_1)
        REFERENCES public.courses(course_id),

    CONSTRAINT fk_risk_course_2
        FOREIGN KEY (course_id_2)
        REFERENCES public.courses(course_id),

    CONSTRAINT valid_severity
        CHECK (severity IN ('Low', 'Medium', 'High')),

    CONSTRAINT different_courses
        CHECK (course_id_1 <> course_id_2)
);

ALTER TABLE public.risk_rules ENABLE ROW LEVEL SECURITY;


CREATE TABLE IF NOT EXISTS public.student_profiles (
    student_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    major VARCHAR(100) NOT NULL,
    academic_level VARCHAR(30) NOT NULL,
    completed_courses JSONB DEFAULT '[]'::jsonb,
    selected_crns JSONB DEFAULT '[]'::jsonb,

    CONSTRAINT valid_academic_level
        CHECK (academic_level IN ('Undergraduate', 'Graduate')),

    CONSTRAINT valid_completed_courses
        CHECK (jsonb_typeof(completed_courses) = 'array'),

    CONSTRAINT valid_selected_crns
        CHECK (jsonb_typeof(selected_crns) = 'array')
);

ALTER TABLE public.student_profiles ENABLE ROW LEVEL SECURITY;
