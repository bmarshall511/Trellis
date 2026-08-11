---
name: security
description: Use when handling user input, authentication, authorisation, secrets, file uploads, or database queries. Also when adding a dependency, exposing an endpoint, or reviewing whether something is safe to ship.
---

# Security

Most breaches are not clever. They are a missing authorisation check, a secret in a repository, or a
dependency nobody looked at. Get the ordinary things right consistently and you have avoided almost
everything that actually happens.

## Authorisation

**Check on every request, at the point the data is accessed.**

The single most common serious bug in a web application is an authorisation check that runs somewhere the
attacker doesn't have to go through. A check in the interface layer protects the interface. A check in
routing or middleware protects the routes that happen to be matched by that configuration — and a
configuration is one edit away from not matching.

Put the check where the data is read or written, so there is no path that reaches the data without it. If
the datastore can enforce it directly, let it: a rule the database enforces cannot be bypassed by a new
code path someone adds next month.

**Check that *this* user may access *this* record.** Being logged in is authentication. Being allowed to
see invoice 4,102 is authorisation. Confusing the two is how one user reads another's data by changing a
number in a URL.

**Deny by default.** New endpoints and new fields start inaccessible and are opened deliberately.

**Test the denial.** A test proving an authorised user can see their data proves nothing about isolation.
Test that someone else cannot.

## Input

Treat everything from outside as hostile: form fields, URLs, headers, uploaded files, webhook payloads,
and anything that came from a third-party API.

**Validate at the boundary, against a schema**, and work with the validated result. Check type, shape,
range and length — not just presence.

**Never build a query by concatenating strings.** Use parameterised queries, always, including for
"internal" values and admin tools. This has been the same bug for thirty years.

**Escape on output, appropriate to the destination.** The rules differ for HTML, attributes, URLs, and
shell commands. Rendering user content as raw markup is how one user's input becomes script running in
another user's session.

**Validate identifiers you use to look things up.** An ID from a request is a claim, not a fact.

**Never pass user input to a shell.** If you genuinely must invoke a command, pass arguments as a list and
never through a shell string.

## Secrets

- Secrets never enter the repository. Not in code, not in config, not in a comment, not in a test fixture
- Secrets never appear in logs, error messages, or anything sent to the client
- Anything reaching a browser is public — a "hidden" field, a minified bundle, and an environment variable
  compiled into client code are all readable
- A leaked secret is rotated, not deleted from the file. It exists in history and in every clone
- Different credentials per environment, always. One credential that works everywhere means a development
  mistake reaches production

## Dependencies

A dependency is code you did not write, running with your permissions, updated by someone you have not met.

- Add one only when it earns its place. Ten lines you own beats a package you must track forever
- Look before adding: is it maintained, widely used, and reasonably scoped?
- Commit the lockfile and install from it in automated environments
- Update deliberately and read what changed. Automatic updates of everything are their own risk
- **Never add a dependency during an unattended run.** Stop and ask. Supply-chain attacks work precisely
  because a new package looks routine in a diff

## Uploads

- Validate the actual content, not the filename or the declared type. Both are attacker-controlled
- Cap the size before reading, not after
- Never execute or interpret an uploaded file
- Store outside the web root, or somewhere that cannot serve executable content
- Generate your own storage names. A user-supplied filename is a path traversal waiting to happen
- Strip metadata from images — photographs commonly carry location
- Serve user content from a different origin than your application where you can, so a malicious file
  cannot act with your application's privileges

## Sessions and authentication

- Never store passwords reversibly. Use a current password-hashing algorithm, never a general-purpose hash
- Issue a new session identifier on login and destroy it on logout
- Session cookies: HTTP-only, secure, and same-site
- Rate-limit authentication, password reset, and anything that sends email or costs money
- Do not reveal whether an account exists in login or reset responses
- Expire sessions, and let a user end all of them

## Errors and logging

- Users get a message that helps them. Logs get the detail
- Never return a stack trace, query, or internal path to a client
- Never log secrets, tokens, passwords, or full payment details
- Log enough to reconstruct what happened: who, what, when, and the outcome
- Log authorisation failures. Repeated ones are the signal that someone is probing

## Before shipping

- [ ] Every endpoint checks that this user may do this to this record
- [ ] There is a test proving an unauthorised user is refused
- [ ] All input validated at the boundary against a schema
- [ ] No string-built queries anywhere
- [ ] No secrets in the diff — check the test fixtures too
- [ ] New dependencies justified, or none added
- [ ] Uploads validated by content, stored under generated names
- [ ] Errors reveal nothing internal
- [ ] Anything expensive or email-sending is rate-limited

## Do not

- Rely on the interface to enforce a rule — anything the browser does, an attacker can skip
- Trust a value because your own code sent it
- Roll your own cryptography, session handling, or password hashing
- Disable certificate verification to make something work
- Leave a debug flag, seeded account, or test bypass reachable in production
- Assume something is safe because it is behind a login. Most attackers have an account
