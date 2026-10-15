# Documentation

Read when a brief changes behaviour that documents describe, when writing or auditing a README, a guide or an AGENTS.md, and when reviewing documentation in a round or a close-out.

## Which carrier holds which fact

| Carrier | Holds | Keeps out |
| --- | --- | --- |
| Root AGENTS.md | Short rules every task needs, a map of the repository, the check commands | Long examples, incident stories, procedures for one situation |
| Subdirectory AGENTS.md | Rules that hold only in that directory | Anything the root already says |
| Architecture document | How the parts fit, the main data flows, where to extend | Every type, every package's internals |
| Module README | Use, configuration, behaviour, failures, limits, effect on consumers | Other modules, copies of interface comments or generated lists |
| Interface comment | What a caller must know: conditions, return values, failures, ordering, ownership | Long history, architecture already explained elsewhere |
| Tutorial | Prerequisites, ordered steps, the visible sign of success, recovery from common failures | Exhaustive option lists |
| Reference | Current behaviour for one topic, organised by the questions readers ask | Teaching sequences, other topics |
| Decision note | The reason for a decision, the alternatives, the cost, the verification | Task logs, plans that already happened |
| Postmortem | Timeline, evidence, cause, impact, prevention | Implementation detail with no causal role |
| Generated reference | What can be produced from code or metadata | Any hand-maintained copy |
| Work records | What an agent did, when, with which evidence | Statements of current behaviour |

One fact has one home, and other places link to it. A condition a caller must not miss, such as a cancellation rule or who owns a resource, may be repeated at the call site; removing it to avoid repetition invites misuse. Claude Code's documentation warns that two contradicting instructions may be resolved either way, so a rule stated twice will eventually be stated two different ways.

## Writing a page

- Decide the reader, the page's one job and its place first. A page above others explains roles and relations and links down for detail.
- A tutorial follows prerequisites and order. A reference follows the reader's questions. Split a page that mixes both at length.
- Ordinary documents describe the current state. History belongs in notes, postmortems and upgrade guides.
- Before giving install or usage instructions, establish what the thing is: an application, a library, a plugin or a configuration. Instructions copied from a neighbouring package are a common error.
- A breaking change visible to users, such as a command, a configuration key, a file format or a published interface, gets a short upgrade section: who is affected, old and new behaviour, the steps in order, and how to confirm the migration worked. The reasons go into a note.

## Checking claims

Run every command, configuration and default the page states, in the form the page shows it. Take fields, defaults, failures and platform differences from the code, the tests or an actual run, never from memory or a similar project.

A claim that cannot be reproduced is deleted or corrected; the test is never adjusted to fit the text. Only a claim that depends on credentials or a network the writer lacks may stay unverified, marked as such, with the person or check that will verify it named. Formatting and link checks do not show that a document is correct.

## Generated content and moves

Edit the source of generated content, such as a template, a schema or a docstring, and regenerate. Never hand-edit generated output or keep a hand-written list that the code could produce. When moving or renaming a page, fix every link to it in the same change; `repo_check.py --only links` finds the broken ones.

## Size of standing files

Codex stops adding AGENTS.md files once the chain from the root to its working directory reaches 32768 bytes. Claude Code's documentation targets under 200 lines per instruction file and loads imported files at startup as well, so an import does not save context. Keep the root AGENTS.md near 100 lines as a map: one line per area, linking to the document that holds the detail. Before trimming, move content to its home and remove repetition; do not cut conditions, failures or ownership to meet a size.

## Auditing documents

An audit across the repository goes to a read-only search subagent with a runbook that lists the pages, the code they describe and the commands to run. It returns each mismatch with the page, the line, the code location and the evidence. The fixes go to Codex as a brief whose write set is the pages. An audit reports; it never rewrites on its own.
