# Configure the header and navigation

The shared header owns the uploaded logo, desktop megamenu and mobile burger
menu. Pages inherit it from `core/base.html`. Do not rebuild it in a page
template.

## Use the control panel

Open **Site core > Site configuration** in the admin.

- **Enable header logo** switches the uploaded mark on or off. When it is off,
  or no file is uploaded, the site name is shown as text.
- **Header logo** accepts an image upload. Add accurate alt text that identifies
  the organisation or mark.
- **Enable megamenu** switches between the configurable grouped menu and the
  compact built-in navigation.
- **Navigation menu label** names the trigger for desktop and assistive
  technology. Keep it short, such as “Menu” or “Explore”.
- **Navigation items** are edited inline on the same screen. Items with the
  same group name form one megamenu column. `sort_order` controls both column
  discovery and link order.

Choose an automatic page when the link points to a route owned by the
skeleton. Automatic items inherit feature visibility. For example, an Articles
item disappears when articles are switched off. Use Custom URL for another
local path or a deliberate external destination.

The description is optional. It appears below the link label in the megamenu
and should explain the destination in one short sentence.

## Change the implementation

`NavigationItem` in `core/models.py` is the source of editable links.
`site_settings()` in `core/context_processors.py` resolves automatic URLs,
removes items whose feature is unavailable and groups the remainder for the
template. `core/base.html` renders that prepared data. `topbar.js` owns open,
close, Escape-key and focus-return behaviour. `base.css` owns the desktop
panel and mobile layout.

When adding a new automatic destination:

1. Add a page constant and choice to `NavigationItem`.
2. Map it to a named URL in `NAVIGATION_ROUTES`.
3. Extend `_navigation_item_visible()` when authentication or a feature switch
   controls the page.
4. Add a starter record in `ensure_starter_content()` when new installations
   should receive the link.
5. Create a migration and test both switch states.

Do not resolve URLs in the template, duplicate feature checks in the template,
or add one-off navigation links to `base.html`. A disabled feature must not
leave a dead link in either menu mode.

## Interaction and accessibility contract

The menu button is a real button with `aria-expanded` and `aria-controls`.
The panel closes on Escape and returns focus to the trigger. Mobile targets are
at least 58 pixels high. Motion uses transform and opacity only, stays within
the design-system G1 timing band and becomes effectively instant when reduced
motion is requested.

Keep these behaviours intact when restyling. Test keyboard access, focus rings,
long translated labels, dark mode, large text and a narrow viewport before
shipping.
