---
name: accessibility
description: Use when building or reviewing any user interface — forms, dialogs, menus, tables, custom controls. Also when choosing colours, when an accessibility check fails, or when deciding whether markup is semantic enough.
---

# Accessibility

Target is **WCAG 2.2 Level AA** everywhere. A project may declare `AA+` in `trellis.json`, which means AA
plus a named subset of AAA criteria recorded in `docs/decisions/`.

## What automation cannot tell you

Automated checks catch roughly a third of real accessibility problems. They find a missing label; they
cannot tell you the label is wrong. Passing the gate is the floor, not the goal.

These require a human or a deliberate manual pass, and no scanner substitutes:

- **Keyboard only.** Unplug the mouse. Can you reach and operate everything? Can you see where you are?
- **Focus order.** Does it follow the visual order, or jump around?
- **Zoom to 400%.** Does content reflow, or does it need horizontal scrolling?
- **A screen reader.** Does what it announces match what the screen shows?
- **Meaningful names.** "Click here" passes every automated check and helps nobody.

## The rules that prevent most problems

**Use the right element.** A `<button>` is focusable, keyboard-operable, and announced as a button, for
free. A `<div>` with a click handler is none of those and needs a role, a tabindex, and key handlers to
approximate what you threw away. The most common accessibility bug is a clickable thing that isn't a
button or a link.

**Links go somewhere. Buttons do something.** If it changes the URL it is a link. If it performs an
action it is a button. This is not styling — it determines keyboard behaviour and what gets announced.

**Every input has a real label**, programmatically associated. Placeholder text is not a label — it
vanishes on focus, exactly when it is needed.

**Never remove a focus indicator** without replacing it with something more visible. `outline: none` with
no replacement makes an interface unusable by keyboard. If the default is ugly, design a better one.

**Never convey meaning by colour alone.** Red text for an error also needs words. A coloured status dot
also needs a label.

**Every image needs alt text that serves its purpose** — describing it if it carries meaning, empty if it
is decorative. Empty alt is correct and common; missing alt is not.

**Announce what changed.** When content updates without a page load — a validation error, a saved
confirmation, results filtering — a screen reader user gets no signal unless you provide one. This is
where accessibility and the feedback rules meet: the same event needs a visual *and* an announced change.

## Contrast

- **Body text:** 4.5:1 minimum
- **Large text** (24px, or 19px bold): 3:1
- **Interactive controls and their focus indicators:** 3:1 against what surrounds them
- **AAA, if declared:** 7:1 body, 4.5:1 large

Check contrast when choosing colours, not after building. Retrofitting a palette that fails means
redesigning, and 7:1 in particular constrains a palette hard — decide it at the start or not at all.

Disabled controls are exempt, which is often abused. If information matters, it should not be
unreadable.

## Forms

Forms are where accessibility most often breaks, and where the cost of breaking it is highest.

- Label every field, visibly
- Mark required fields in text, not only with an asterisk or a colour
- Put the error next to the field it belongs to, and describe how to fix it
- Associate errors with their input so they are announced on focus
- Move focus to the first error on a failed submit, or announce a summary
- Never clear what the user typed because validation failed
- Group related controls, and give the group a name

## Custom controls

Before building a custom dropdown, dialog, tab set, or combobox: **use the native element if one exists.**
Native controls come with keyboard behaviour, screen-reader semantics, and mobile handling that take
serious effort to reproduce and are usually reproduced badly.

If you must build one, it needs: the correct role, the full keyboard interaction pattern for that role
(arrow keys, Home/End, Escape, Enter), managed focus, and state communicated programmatically as well as
visually. Follow the established pattern for that control — do not invent one.

**Dialogs specifically**, because they are the most commonly broken: focus moves into the dialog on open,
is trapped while it is open, Escape closes it, and focus returns to whatever opened it. Content behind it
is hidden from assistive technology, not merely visually covered.

## WCAG 2.2 additions worth knowing

These are newer and frequently missed:

- **Target size** — interactive targets at least 24×24px, or adequately spaced
- **Focus not obscured** — a focused element must not be hidden behind a sticky header or floating bar
- **Dragging alternatives** — anything draggable needs a non-drag way to do the same thing
- **Consistent help** — help mechanisms appear in the same relative place across pages
- **Redundant entry** — do not ask for the same information twice in one process
- **Accessible authentication** — no cognitive-function test (like remembering a code) without an
  alternative. This rules out several common login patterns

## Testing

Automated checks run as the `a11y` gate and must pass — but treat a pass as "no obvious errors", not "this
is accessible".

Write tests that assert behaviour rather than markup: that a dialog traps focus, that an error is
announced, that a menu is operable by keyboard. Those catch regressions that a scanner never will.

## Do not

- Add `role="button"` to a `div` instead of using a `button`
- Use `aria-label` to paper over markup that should have been semantic
- Add ARIA that duplicates what the element already communicates — incorrect ARIA is worse than none
- Set `tabindex` above 0
- Hide something visually in a way that also hides it from screen readers, when it was meant to be read
- Turn off zoom or pinch on mobile
- Treat a green automated check as proof
