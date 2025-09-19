# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI Social Support application with a clear separation between backend and frontend components. The project structure suggests a conversational AI system designed to provide social support services.

## Architecture

The project follows a modular architecture:

### Backend Structure
- `backend/agents/` - AI agent implementations and conversation logic
- `backend/api/` - REST API endpoints and route handlers
- `backend/models/` - Data models and database schemas
- `backend/services/` - Business logic and external service integrations
- `backend/utils/` - Shared utilities and helper functions

### Frontend Structure
- `frontend/` - User interface components and client-side application

### Data Management
- `data/synthetic/` - Generated training data and synthetic conversations
- `data/templates/` - Message templates and conversation patterns

### Documentation
- `docs/` - Project documentation and API specifications

## Development Guidelines

When working on this codebase:

1. **Backend Development**: Place AI-related logic in `agents/`, API routes in `api/`, and shared business logic in `services/`

2. **Data Handling**: Use `data/templates/` for conversation templates and `data/synthetic/` for training data

3. **Modularity**: Keep components loosely coupled - agents should communicate through well-defined interfaces

4. **API Design**: Design RESTful endpoints in the `api/` directory that can support conversational flows

## Technology Stack

The project structure suggests support for:
- Conversational AI agents
- Template-based response generation
- Synthetic data generation for training
- Modular service architecture

Note: Specific build commands, test frameworks, and dependencies will be added as the project develops and package.json/requirements files are created.