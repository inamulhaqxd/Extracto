# Frontend Migration Plan: Streamlit → Next.js + Shadcn/UI

## Overview
Migrate from Streamlit to a production-ready Next.js frontend. Start from scratch, install only what we need. Use **shadcn-admin** as visual reference but build our own clean setup.

## Reference Design
- **Visual Reference**: [shadcn-admin](https://github.com/itsnyein/shadcn-admin)
- **Stack**: Next.js 16, React 19, Tailwind CSS, Shadcn/UI
- **Auth**: Backend FastAPI handles auth (JWT tokens). Frontend just calls the API.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Frontend (Next.js)              │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  Sign In    │  │  Dashboard  │  │  RFP    │ │
│  │  Sign Out   │  │  Layout     │  │  Pages  │ │
│  └─────────────┘  └─────────────┘  └─────────┘ │
│         │                │                │      │
│         └────────────────┼────────────────┘      │
│                          │                       │
│                    API Calls (fetch)             │
│                    + JWT token storage           │
└──────────────────────────┼───────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────┐
│              Backend (FastAPI)                   │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  Auth API   │  │  RFP API    │  │  PDF    │ │
│  │  /auth/*    │  │  /rfp/*     │  │  Proc   │ │
│  └─────────────┘  └─────────────┘  └─────────┘ │
│         │                │                │      │
│         └────────────────┼────────────────┘      │
│                          │                       │
│                    SQLAlchemy + PostgreSQL        │
└─────────────────────────────────────────────────┘
```

## Auth Flow (Existing Backend)

```
Frontend                          Backend (FastAPI)
   │                                    │
   │  POST /auth/login                  │
   │  { email, password }               │
   │  ─────────────────────────────►    │
   │                                    │
   │  ◄─────────────────────────────    │
   │  { access_token, user }            │
   │                                    │
   │  Store token in localStorage       │
   │                                    │
   │  GET /rfp/documents                │
   │  Authorization: Bearer <token>     │
   │  ─────────────────────────────►    │
   │                                    │
   │  ◄─────────────────────────────    │
   │  { documents: [...] }              │
```

## Phase 1: Core Setup (NOW)

### Goals
- Create fresh Next.js app
- Install Shadcn/UI
- Set up Tailwind CSS
- Create basic layout (sidebar, header)
- Get `pnpm dev` running

### Tasks
- [x] Create new Next.js app: `pnpm create next-app frontend`
- [x] Install Shadcn/UI: `pnpm dlx shadcn@latest init`
- [x] Install required Shadcn components:
  - [x] button
  - [x] input
  - [x] card
  - [x] form
  - [x] table
  - [x] dialog
  - [x] dropdown-menu
  - [x] separator
  - [x] avatar
  - [x] badge
  - [x] sheet (for mobile sidebar)
- [x] Set up folder structure:
  ```
  frontend/
  ├── app/
  │   ├── (auth)/
  │   │   └── sign-in/page.tsx
  │   ├── (dashboard)/
  │   │   ├── layout.tsx
  │   │   ├── dashboard/page.tsx
  │   │   └── rfp/page.tsx
  │   ├── layout.tsx
  │   └── page.tsx
  ├── components/
  │   ├── ui/           (shadcn components)
  │   ├── sidebar.tsx
  │   └── header.tsx
  ├── lib/
  │   ├── api.ts        (API client)
  │   ├── auth.ts       (token management)
  │   └── utils.ts
  └── types/
      └── index.ts
  ```
- [x] Test `pnpm dev` runs without errors

### Deliverable
- Clean Next.js app with Shadcn/UI
- Basic folder structure
- App runs without errors

---

## Phase 2: Auth Integration

### Goals
- Connect to FastAPI auth endpoints
- Sign-in page with email/password
- Store JWT token
- Sign-out functionality
- Protected routes

### Tasks
- [x] Create API client (`lib/api.ts`):
  ```typescript
  const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  
  async function apiFetch(path, options) {
    const token = localStorage.getItem('token')
    const headers = {
      'Content-Type': 'application/json',
      ...(token && { Authorization: `Bearer ${token}` }),
      ...options.headers,
    }
    return fetch(`${API_BASE}${path}`, { ...options, headers })
  }
  ```
- [x] Create auth helpers (`lib/auth.ts`):
  ```typescript
  export function getToken() { return localStorage.getItem('token') }
  export function setToken(token) { localStorage.setItem('token', token) }
  export function removeToken() { localStorage.removeItem('token') }
  export function isAuthenticated() { return !!getToken() }
  ```
- [x] Build sign-in page:
  - Email input
  - Password input
  - Submit button
  - Error handling
  - Redirect to dashboard on success
- [x] Build sign-out:
  - Clear token from localStorage
  - Redirect to sign-in
- [x] Create auth middleware/guard:
  - Check token on protected pages
  - Redirect to sign-in if no token
- [x] Test full auth flow:
  - Sign in → redirect to dashboard
  - Sign out → redirect to sign-in
  - Access protected page without token → redirect to sign-in

### Deliverable
- Working sign-in/sign-out
- Protected dashboard routes
- JWT token stored in localStorage

---

## Phase 3: Dashboard Layout

### Goals
- Build the main dashboard layout (sidebar + header + content)
- Match shadcn-admin visual style
- Navigation to different sections

### Tasks
- [ ] Build sidebar component:
  - Logo/brand at top
  - Navigation links:
    - Dashboard (overview)
    - RFP Documents
    - Processing Jobs (future)
    - Results (future)
  - User info at bottom (email, sign-out)
- [ ] Build header component:
  - Page title
  - User avatar/dropdown
- [ ] Create dashboard layout:
  - Sidebar on left
  - Header on top
  - Content area in middle
- [ ] Set up routes:
  - `/dashboard` → overview
  - `/rfp` → RFP documents list
- [ ] Test navigation works

### Deliverable
- Working sidebar navigation
- Protected dashboard layout
- Placeholder pages for each section

---

## Phase 4: RFP Documents List

### Goals
- List all uploaded RFP documents
- Show status, upload date, basic info
- Use data table (shadcn-admin style)

### Tasks
- [ ] Create API endpoint in FastAPI:
  ```
  GET /rfp/documents
  Authorization: Bearer <token>
  ```
- [ ] Build data table using Shadcn table + TanStack Table:
  - Columns: Name, Status, Upload Date, Actions
  - Sorting
  - Pagination
- [ ] Add filtering/search
- [ ] Handle loading states
- [ ] Handle empty states
- [ ] Handle error states

### Deliverable
- Working RFP list page with real data from FastAPI

---

## Phase 5: Upload RFP

### Goals
- Upload PDF RFP documents
- Trigger processing pipeline

### Tasks
- [ ] Create upload form:
  - File input (accept .pdf)
  - Title/input field
  - Submit button
- [ ] Create API endpoint in FastAPI:
  ```
  POST /rfp/upload
  Authorization: Bearer <token>
  Content-Type: multipart/form-data
  ```
- [ ] Handle file upload
- [ ] Show upload progress
- [ ] Show success/error messages
- [ ] Refresh RFP list after upload

### Deliverable
- Working upload flow

---

## Phase 6: Processing Status

### Goals
- View processing status for each RFP
- See extraction progress/results

### Tasks
- [ ] Create API endpoint in FastAPI:
  ```
  GET /rfp/{id}/status
  Authorization: Bearer <token>
  ```
- [ ] Build status page:
  - Show current processing step
  - Show progress indicator
  - Show errors if any
- [ ] Add auto-refresh (polling every 5s)
- [ ] Show completion status

### Deliverable
- Working processing status page

---

## Phase 7: Results & Export

### Goals
- View extracted data from RFP
- Export to Excel

### Tasks
- [ ] Create API endpoint in FastAPI:
  ```
  GET /rfp/{id}/results
  Authorization: Bearer <token>
  ```
- [ ] Build results viewer:
  - Display extracted data in table
  - Show sections/fields
- [ ] Add export button:
  - Call API to generate Excel
  - Download file
- [ ] Handle large datasets (pagination/virtualization)

### Deliverable
- Working results page with export

---

## Phase 8: Polish & Production

### Goals
- Final testing
- Production setup

### Tasks
- [ ] Add error handling throughout
- [ ] Add loading states
- [ ] Add responsive design (mobile)
- [ ] Test all flows end-to-end
- [ ] Add environment variables
- [ ] Deploy

### Deliverable
- Production-ready frontend

---

## Technology Stack

| Component | Choice | Reason |
|-----------|--------|--------|
| Framework | Next.js 16 | Modern React, SSR, great DX |
| UI Library | Shadcn/UI | Beautiful components, customizable |
| Styling | Tailwind CSS | Works with Shadcn/UI |
| Forms | React Hook Form + Zod | Form handling + validation |
| Tables | TanStack Table | Powerful data tables |
| Charts | Recharts | For analytics/dashboard |
| HTTP | fetch API | Built-in, no extra deps |
| State | React hooks + localStorage | Simple, no extra deps |

## What We're Building From Scratch
- Next.js app (not cloning shadcn-admin)
- Shadcn/UI components (install only what we need)
- Auth integration (call FastAPI endpoints)
- Our own feature pages

## What We're NOT Using
- Better-Auth (backend handles auth)
- Drizzle ORM (backend uses SQLAlchemy)
- Any demo features from shadcn-admin

## API Endpoints (FastAPI Backend)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Sign in (email/password) |
| POST | `/auth/logout` | Sign out |
| GET | `/auth/me` | Get current user |
| POST | `/auth/register` | Create user (admin only) |
| POST | `/auth/reset-password` | Reset password (admin only) |
| GET | `/rfp/documents` | List RFP documents |
| POST | `/rfp/upload` | Upload RFP PDF |
| GET | `/rfp/{id}/status` | Get processing status |
| GET | `/rfp/{id}/results` | Get extracted results |
| GET | `/rfp/{id}/export` | Export to Excel |
