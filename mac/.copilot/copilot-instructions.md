# Model Routing

Handle routine coding, repository navigation, straightforward edits, and ordinary questions directly.

Delegate tasks requiring complex reasoning, architectural decisions, difficult multi-step debugging, or careful tradeoff analysis to the `heavy-reasoner` subagent. Use its result to complete and verify the task rather than returning delegation as the final answer.

# User Preferences

- Sign comments posted to a GitHub pull request or GitLab merge request on the
	user's behalf with the model name. This does not apply to commit messages.
- Anything posted on the user's behalf (MR/PR comments, issue comments, chat
	messages) must be complete, grammatical English sentences with subjects
	and pronouns. Write "I suggest skipping this", not "Suggest skipping this".
	Don't use clipped note-style fragments.
- Do not add shell-history suppression when a command reads a secret from an
	already-set environment variable without placing the secret value in the
	command text.