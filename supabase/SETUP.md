
# SmartAdvisor Supabase Setup Guide

## Purpose

This guide explains how to set up the SmartAdvisor development database using Supabase.

The database stores course information, class sections, compatibility risk rules, and synthetic student profiles.

## Requirements

- A Supabase account
- Access to a Supabase project
- The SmartAdvisor backend repository
- SQL migration file in supabase/migrations/

## 1. Create a Supabase Project

1. Sign in at https://supabase.com/dashboard
2. Create a new project or open the team's existing project.
3. Select the appropriate database region.
4. Save the database password securely.
5. Wait until the database status is Healthy.

## 2. Create the Database Tables

1. Open the Supabase project dashboard.
2. Select SQL Editor.
3. Create a new query.
4. Open supabase/migrations/20261009_initial_schema.sql.
5. Copy the SQL into the Supabase SQL Editor.
6. Click Run.

The migration creates these tables:

- courses
- sections
- risk_rules
- student_profiles

All four tables have Row Level Security enabled.

## 3. Verify the Tables

1. Open Table Editor.
2. Select the public schema.
3. Confirm that all four tables appear.

## 4. Configure Environment Variables

The project includes a .env.example template.

Copy it to a local file named .env if database access is required.

Configure the appropriate Supabase project URL and API key using the Supabase dashboard.

Never commit actual passwords or secret API keys to GitHub.

## 5. Run the Backend Locally

Install dependencies:

    python -m pip install -r requirements.txt

Start FastAPI:

    python -m uvicorn backend.api:app --reload

Open Swagger documentation:

    http://127.0.0.1:8000/docs

Verify the health endpoint:

    http://127.0.0.1:8000/health

## 6. Database Security

- Row Level Security is enabled on all four tables.
- Access policies must be configured before client access.
- Do not expose database passwords or secret API keys.
- Use synthetic student records for development and testing.
- Grant only the database permissions required by the application.

## 7. Current Implementation Status

The Supabase schema has been created and verified in the SmartAdvisor-Development project.

The existing FastAPI backend currently retrieves course records from the FAU Excel dataset.

The database import pipeline and FastAPI-to-Supabase integration still need to be implemented and tested.
