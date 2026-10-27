# CivicPulse

## Overview
CivicPulse is a hosted chat agent that helps citizens analyze civic complaints before filing them with their municipality. Describe an issue in plain text and CivicPulse identifies the category, points to the responsible municipal department, assigns a priority score from 0 to 100 with an explanation, and suggests one concrete next action. Replies are generated with ASI:One using the complaint and the session history, with a local keyword-based fallback when the model call fails.

## Features
- Category detection for potholes, garbage, broken streetlights, water leakage, and blocked drains (plus Other)
- Department routing for each issue type
- Priority score 0-100 with consistent bands: 80-100 immediate safety hazard, 50-79 significant disruption, 20-49 moderate inconvenience, 0-19 minor cosmetic
- Plain-language explanation of the score and one concrete suggested next action
- Session-aware follow-up questions using conversation history
- Keyword-based fallback analysis when the ASI:One call is unavailable
- Friendly greeting and help handling

## Limitations
- ASI:One usage is metered against the owner's LLM token quota
- The fallback scorer is keyword-based and approximate; it never sees photos or exact locations
- Priority bands are advisory; the municipality's own triage rules take precedence