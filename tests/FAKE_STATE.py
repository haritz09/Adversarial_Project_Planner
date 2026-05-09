FAKE_STATE = {
    "raw_input": "Build a real-time chat application in 3 weeks with 2 developers. Must integrate with our existing OAuth system.",
    "project_context": {
        "goal": "real-time chat application",
        "timeline": "3 weeks",
        "team_size": 2,
        "constraints": ["must integrate with existing OAuth system"],
        "stack": None,
        "methodology": None,
    },
    "user_provided_fields": {
        "goal": True,
        "timeline": True,
        "team_size": True,
        "stack": False,
        "methodology": False,
    },
    "debate1_arguments": [
        {
            "agent": "A",
            "argument": "I propose React + Firebase for this project. Firebase's Realtime Database handles WebSocket connections natively, eliminating backend complexity. With 2 devs and a 3-week timeline, Firebase Auth can wrap the existing OAuth provider in under a day, keeping the integration constraint manageable.",
            "round": 1,
        },
        {
            "agent": "B",
            "argument": "Firebase is a reasonable choice but introduces vendor lock-in and limited query flexibility. I propose React + Node.js + Socket.io + PostgreSQL instead. The existing OAuth integration will be cleaner with a custom Node.js middleware layer, and PostgreSQL gives us full control over message history queries and future feature extensions.",
            "round": 1,
        },
        {
            "agent": "A",
            "argument": "The vendor lock-in concern is valid for a long-term product, but for a 3-week MVP with 2 developers, Node.js + PostgreSQL adds significant setup overhead — connection pooling, ORM configuration, Socket.io scaling. Firebase lets us ship a working product in week 1 and iterate. Lock-in can be addressed post-MVP if needed.",
            "round": 2,
        },
        {
            "agent": "B",
            "argument": "After reconsideration, the timeline argument is compelling. However, I'd suggest a middle ground: React + Firebase Realtime Database for messaging, but keep authentication as a custom Node.js middleware to cleanly handle the OAuth constraint. This reduces lock-in risk on the auth layer while keeping Firebase's real-time advantages.",
            "round": 2,
        },
    ],
    "debate1_rounds": 3,
    "debate1_decision": "React + Firebase Realtime Database + Node.js OAuth middleware",
    "debate1_judge_rationale": "Agent B's final proposal provides the best balance: Firebase handles real-time messaging with minimal setup, while a thin Node.js OAuth middleware cleanly satisfies the existing auth integration constraint. This avoids the full vendor lock-in risk on the auth layer while keeping the 3-week timeline achievable for a 2-person team.",
    "debate1_winner": "B",
    "debate1_needs_another_round": False,
    "debate1_agent_a_score": 7,
    "debate1_agent_b_score": 9,
 
    "architecture_doc": """\
## Chosen Stack
 
- **Frontend**: React 18 with TypeScript — component-based UI, strong ecosystem, both devs familiar
- **Real-time messaging**: Firebase Realtime Database — handles WebSocket connections natively, no infrastructure setup required
- **Authentication**: Node.js + Express middleware — wraps the existing OAuth provider, issues JWT tokens consumed by both React and Firebase
- **Hosting**: Firebase Hosting (frontend) + Cloud Run (Node.js auth service)
 
## System Components
 
- **React Client** — UI layer, connects directly to Firebase Realtime Database for chat, calls Node.js auth service for login/logout
- **Firebase Realtime Database** — stores and syncs chat messages in real time, enforces read/write rules via Firebase Security Rules
- **Node.js Auth Service** — OAuth 2.0 integration with existing provider, exchanges OAuth tokens for Firebase custom tokens and JWTs
- **Firebase Security Rules** — ensures users can only read/write their own conversations
- **Cloud Run** — hosts the Node.js auth service, autoscales to zero when idle
 
## Key Architectural Decisions
 
1. **Firebase over custom WebSocket server**: eliminates week 1 infrastructure setup, acceptable trade-off for 3-week timeline
2. **Node.js auth middleware as a separate service**: decouples auth from Firebase, allowing OAuth integration without modifying the existing provider
3. **JWT tokens as the auth bridge**: Node.js issues JWTs that Firebase verifies via custom token minting, avoiding double auth flows
4. **Firebase Security Rules as the authorization layer**: business logic for message access control lives in rules, not in application code
5. **Cloud Run for auth service**: serverless deployment, no infrastructure management, scales automatically
 
## Risks & Mitigations
 
| Risk | Mitigation |
|---|---|
| Firebase Realtime Database query limitations for message history | Design data structure upfront; use indexed queries; plan migration to Firestore if needed post-MVP |
| OAuth integration complexity consuming more than 1 day | Timebox to day 2; if blocked, use Firebase Auth with OAuth provider directly as fallback |
| Firebase Security Rules misconfiguration exposing data | Write rules in week 1 alongside data model; test with Firebase emulator before deploying |
""",
 
    "scope_doc": """\
## Objectives
 
1. Deliver a functional real-time chat application within 3 weeks with 2 developers
2. Integrate seamlessly with the existing OAuth authentication system
3. Support one-to-one private messaging as the core MVP feature
4. Achieve message delivery latency under 500ms under normal network conditions
5. Deploy to a production-ready environment by the end of week 3
 
## MVP Definition
 
The MVP includes the following features:
 
- **Authentication**: Login and logout via existing OAuth provider; session persistence across page refreshes
- **Contact list**: Display a list of users the authenticated user can chat with
- **One-to-one messaging**: Send and receive text messages in real time
- **Message history**: Load the last 50 messages when opening a conversation
- **Online presence**: Show whether a contact is currently online or offline
- **Basic notifications**: Browser tab title updates when a new message arrives
 
## Out of Scope
 
The following will NOT be built in this version:
 
- Group chats or channels
- File and image sharing
- Push notifications (mobile or desktop)
- Message search
- Read receipts and typing indicators
- Message editing or deletion
- End-to-end encryption
- Mobile native applications
 
## Success Criteria
 
1. Two users can exchange messages in real time with no manual page refresh required
2. OAuth login completes in under 3 seconds on a standard connection
3. Message history loads correctly when reopening a conversation
4. The application handles 2 concurrent users without errors during the demo
5. All MVP features are deployed and accessible via a public URL by end of week 3
""",
 
    "project_plan_doc": """\
## Phases
 
### Phase 1 — Foundation (Days 1–4)
Duration: 3–5 days
Main tasks:
- Set up monorepo with React + TypeScript
- Configure Firebase project (Realtime Database, Hosting, Security Rules emulator)
- Implement Node.js auth service skeleton with OAuth 2.0 flow
- Deploy auth service to Cloud Run (staging environment)
- Establish CI pipeline with basic linting and build checks
 
Deliverable: Both devs can log in via OAuth and receive a valid Firebase custom token
 
### Phase 2 — Core Chat (Days 5–12)
Duration: 6–8 days
Main tasks:
- Design Firebase data model for conversations and messages
- Implement real-time message send and receive
- Build contact list UI with online presence indicators
- Implement message history loading (last 50 messages)
- Write and test Firebase Security Rules
- Basic responsive UI layout
 
Deliverable: Two authenticated users can chat in real time with message history
 
### Phase 3 — Polish & Deploy (Days 13–18)
Duration: 4–6 days
Main tasks:
- Browser tab notification on new message
- Error handling and loading states throughout the UI
- End-to-end testing of the full auth + chat flow
- Performance check: message latency under 500ms
- Deploy frontend to Firebase Hosting (production)
- Smoke test on production environment
 
Deliverable: Production-ready application accessible via public URL
 
## Milestones
 
| Milestone | Target Date | Description |
|---|---|---|
| Auth service deployed | 2025-05-13 | OAuth flow works end-to-end in staging |
| Firebase data model finalised | 2025-05-15 | Schema agreed, Security Rules drafted |
| Real-time messaging working | 2025-05-19 | Two users can chat in development |
| MVP feature complete | 2025-05-23 | All MVP features implemented and tested |
| Production deploy | 2025-05-26 | Application live at public URL |
 
## Time Estimates
 
| Task | Phase | Effort Range |
|---|---|---|
| Monorepo and Firebase setup | Phase 1 | 3–5h |
| OAuth + Node.js auth service | Phase 1 | 4–8h |
| Cloud Run deployment (staging) | Phase 1 | 2–4h |
| Firebase data model design | Phase 2 | 2–3h |
| Real-time messaging (send/receive) | Phase 2 | 4–6h |
| Contact list + presence UI | Phase 2 | 3–5h |
| Message history loading | Phase 2 | 2–4h |
| Firebase Security Rules | Phase 2 | 3–5h |
| UI layout and responsiveness | Phase 2 | 4–6h |
| Notifications + error handling | Phase 3 | 2–4h |
| End-to-end testing | Phase 3 | 3–5h |
| Production deployment | Phase 3 | 2–3h |
 
## Risks
 
| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| OAuth integration takes longer than estimated | Medium | High | Timebox to day 2; use Firebase Auth fallback if blocked |
| Firebase Security Rules misconfiguration | Medium | High | Test with emulator from day 1; review rules together before deploying |
| Scope creep from stakeholder requests | Low | Medium | Share MVP definition document before development starts |
| Real-time performance issues under load | Low | Medium | Test with Firebase emulator early; monitor latency from week 2 |
| Cloud Run cold start delays in auth service | Low | Low | Keep service warm with a scheduled ping if latency becomes an issue |
""",
 
    "notion_parent_page_id": "356ae85ff5738038a2c8e4708b437de2",
    "notion_urls": {},
    "notion_page_ids": {},
    "current_node": "plan_generator",
    "langfuse_session_id": None,
    "trace_ids": None,
    "run_id": "test-run-001",
    "max_rounds": 3,
    "created_at": "2025-05-09T10:00:00Z",
    "updated_at": "2025-05-09T10:05:00Z",
}