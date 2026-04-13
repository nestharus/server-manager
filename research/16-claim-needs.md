# Synthesis: daemon/claim.py Needs

Date: 2026-04-13

## Humility-Specific Needs

1. **Claim operation**: When a handler clicks "Claim" on a queue message, the thread membership narrows from all handler-role members to just claimer + requester + admins. This is the core primitive.

2. **Pre-claim state**: Thread visible to requester + all members of the handler role. For applications: Chapter Officer. For tickets: Staff/Moderator/Chapter Officer depending on type.

3. **Post-claim state**: Thread visible to claimer + requester + admins only. All other handler-role members removed.

4. **Trial Mod read-only**: For moderator tickets, Trial Mod gets VIEW_CHANNEL + READ_MESSAGE_HISTORY but not SEND_MESSAGES on the parent channel. Thread inherits these permissions. This is a parent-channel overwrite, not a thread-membership concern.

5. **Admin detection**: Members with administrator permission should always be retained in threads. Use `member.guild_permissions.administrator`.

6. **Helper layer only**: This is a reusable helper module, not a full ticket/application subsystem. It provides functions that the applications and tickets modules call.

7. **Async**: discord.py thread operations are async (add_user, remove_user), so claim.py functions are async.

## Gaps
None. Research covers discord.py thread API fully.
