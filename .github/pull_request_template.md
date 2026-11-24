## What and why

<!-- What does this change, and why is it needed? Link the issue, for example "Closes #12". -->

## How I tested it

<!-- Commands you ran and what you tried on screen. Screenshots of the fictional sample family only. -->

## Checklist

- [ ] `npm run lint -- --max-warnings 0`, `npm run typecheck`, `npm test`, `npm run build` and `node scripts/check-pii.mjs` pass locally
- [ ] I tried the changed screen in a browser (if the change shows on screen)
- [ ] Tests added or updated for changed behavior
- [ ] README, `SECURITY.md` or `docs/` updated if behavior changed
- [ ] No real names, schools, addresses, calendar links, tokens, PINs or family photos in the code, tests, screenshots or this description
- [ ] This touches auth, the PIN, the bridge, Docker or secrets (`src/proxy.ts`, `src/lib/session.ts`, `src/lib/guard.ts`, `src/lib/auth.ts`, `src/lib/pin-attempts.ts`, `src/lib/safe-fetch.ts`, `src/app/api/`, `bridge/`, `Dockerfile`, `docker-compose*.yml`, `docker/`, `scripts/`, `.github/`) and needs a maintainer review
