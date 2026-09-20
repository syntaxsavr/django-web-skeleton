/* Klaro! configuration, built at runtime from #skeleton-tracking-config
   (rendered by the server from the control panel). A tracker service is
   declared only when its ID is configured; loaders run exclusively inside
   consent callbacks. Google trackers get Consent Mode v2 defaults. */
(function () {
  "use strict";

  function readConfig() {
    var node = document.getElementById("skeleton-tracking-config");
    if (!node) return null;
    try {
      return JSON.parse(node.textContent);
    } catch (e) {
      return null;
    }
  }

  var server = readConfig() || { ids: {}, consentEnabled: false, storageName: "skeleton_consent" };
  var ids = server.ids || {};

  function has(field) {
    return !!(ids[field] && String(ids[field]).trim());
  }

  function injectScript(src, attrs) {
    var script = document.createElement("script");
    script.src = src;
    script.async = true;
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        script.setAttribute(key, attrs[key]);
      });
    }
    document.head.appendChild(script);
  }

  function consentModeDefaults() {
    window.dataLayer = window.dataLayer || [];
    window.dataLayer.push({
      "gtm.consentMode": {
        analytics_storage: "denied",
        ad_storage: "denied",
        ad_user_data: "denied",
        ad_personalization: "denied",
        wait_for_update: 500,
      },
    });
  }

  var LOADERS = {
    google_analytics: function () {
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () {
        window.dataLayer.push(arguments);
      };
      injectScript("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(ids.googleAnalyticsId));
      window.gtag("js", new Date());
      window.gtag("config", ids.googleAnalyticsId, { anonymize_ip: true });
    },
    googletagmanager: function () {
      window.dataLayer = window.dataLayer || [];
      window.dataLayer.push({ "gtm.start": Date.now(), event: "gtm.js" });
      injectScript("https://www.googletagmanager.com/gtm.js?id=" + encodeURIComponent(ids.googleTagManagerId));
    },
    google_ads: function () {
      window.dataLayer = window.dataLayer || [];
      window.gtag = window.gtag || function () {
        window.dataLayer.push(arguments);
      };
      injectScript("https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(ids.googleAdsId));
      window.gtag("js", new Date());
      window.gtag("config", ids.googleAdsId);
    },
    meta_pixel: function () {
      if (window.fbq) return;
      var n = (window.fbq = function () {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      });
      if (!window._fbq) window._fbq = n;
      n.push = n;
      n.loaded = true;
      n.version = "2.0";
      n.queue = [];
      injectScript("https://connect.facebook.net/en_US/fbevents.js");
      window.fbq("init", ids.metaPixelId);
      window.fbq("track", "PageView");
    },
    linkedin: function () {
      window._linkedin_partner_id = ids.linkedinPartnerId;
      window._linkedin_data_partner_ids = window._linkedin_data_partner_ids || [];
      window._linkedin_data_partner_ids.push(ids.linkedinPartnerId);
      injectScript("https://snap.licdn.com/li.lms-analytics/insight.min.js");
    },
    microsoft_ads: function () {
      window.uetq = window.uetq || [];
      (function initUet() {
        var s = document.createElement("script");
        s.src = "https://bat.bing.com/bat.js";
        s.async = 1;
        s.onload = function () {
          var uet = new window.UET({ ti: ids.microsoftUetTagId });
          uet.set("dispatch");
          window.uetq.push(uet);
        };
        document.head.appendChild(s);
      })();
    },
    clarity: function () {
      window.clarity =
        window.clarity ||
        function () {
          (window.clarity.q = window.clarity.q || []).push(arguments);
        };
      injectScript("https://www.clarity.ms/tag/" + encodeURIComponent(ids.clarityProjectId));
    },
    hotjar: function () {
      (function (h, o, t, j, a, r) {
        h.hj =
          h.hj ||
          function () {
            (h.hj.q = h.hj.q || []).push(arguments);
          };
        h._hjSettings = { hjid: Number(ids.hotjarSiteId), hjsv: 6 };
        a = o.getElementsByTagName("head")[0];
        r = o.createElement("script");
        r.async = 1;
        r.src = t + h._hjSettings.hjid + j + h._hjSettings.hjsv;
        a.appendChild(r);
      })(window, document, "https://static.hotjar.com/c/hotjar-", ".js?sv=");
    },
    tiktok: function () {
      window.TiktokAnalyticsObject = "ttq";
      var ttq = (window.ttq = window.ttq || []);
      ttq.methods = ["page", "track", "identify", "instances", "debug", "on", "off", "once", "ready", "alias", "group", "enableCookie", "disableCookie"];
      ttq.setAndDefer = function (obj, method) {
        obj[method] = function () {
          obj.push([method].concat(Array.prototype.slice.call(arguments, 0)));
        };
      };
      for (var i = 0; i < ttq.methods.length; i++) ttq.setAndDefer(ttq, ttq.methods[i]);
      ttq.load = function (id) {
        var url = "https://analytics.tiktok.com/i18n/pixel/events.js";
        ttq._i = ttq._i || {};
        ttq._i[id] = [];
        ttq._i[id]._u = url;
        ttq._t = ttq._t || {};
        ttq._t[id] = +new Date();
        ttq._o = ttq._o || {};
        injectScript(url + "?sdkid=" + encodeURIComponent(id) + "&lib=ttq");
      };
      ttq.load(ids.tiktokPixelId);
      ttq.page();
    },
    pinterest: function () {
      if (window.pintrk) return;
      window.pintrk = function () {
        window.pintrk.queue.push(Array.prototype.slice.call(arguments));
      };
      var n = (window.pintrk = window.pintrk);
      n.queue = [];
      n.version = "3.0";
      injectScript("https://s.pinimg.com/ct/core.js");
      window.pintrk("load", ids.pinterestTagId);
      window.pintrk("page");
    },
    x_pixel: function () {
      if (window.twq) return;
      var twq = (window.twq = function () {
        twq.exe ? twq.exe.apply(twq, arguments) : twq.queue.push(arguments);
      });
      twq.version = "1.1";
      twq.queue = [];
      injectScript("https://static.ads-twitter.com/uwt.js");
      window.twq("init", ids.xPixelId);
      window.twq("track", "PageView");
    },
    matomo: function () {
      window._paq = window._paq || [];
      window._paq.push(["enable_link_tracking", true]);
      window._paq.push(["setTrackerUrl", ids.matomoUrl + "/matomo.php"]);
      window._paq.push(["setSiteId", ids.matomoSiteId]);
      injectScript(ids.matomoUrl + "/matomo.js");
    },
  };

  var googleOn = has("googleAnalyticsId") || has("googleTagManagerId") || has("googleAdsId");

  function service(name, purposes, cookies, title, description) {
    return {
      name: name,
      title: title,
      description: description,
      default: false,
      required: false,
      purposes: purposes,
      cookies: cookies,
    };
  }

  var analyticsServices = [];
  if (has("googleAnalyticsId")) {
    analyticsServices.push(service("google_analytics", ["analytics"], [/^_ga.*$/, /^_gid$/], "Google Analytics", "Traffic statistics with anonymised IP."));
  }
  if (has("googleTagManagerId")) {
    analyticsServices.push(service("googletagmanager", ["analytics"], [/^_ga.*$/], "Google Tag Manager", "Tag management for measurement tools."));
  }
  if (has("clarityProjectId")) {
    analyticsServices.push(service("clarity", ["analytics"], [/^_clck$/, /^_clsk$/], "Microsoft Clarity", "Anonymous session recordings and heatmaps."));
  }
  if (has("hotjarSiteId")) {
    analyticsServices.push(service("hotjar", ["analytics"], [/^_hj.*$/], "Hotjar", "Anonymous heatmaps and behaviour analytics."));
  }
  if (has("matomoUrl")) {
    analyticsServices.push(service("matomo", ["analytics"], [/^_pk_.*$/], "Matomo (self-hosted)", "Privacy-friendly analytics hosted on our own server."));
  }

  var marketingServices = [];
  if (has("googleAdsId")) {
    marketingServices.push(service("google_ads", ["marketing"], [/^_gcl_.*$/, /^IDE$/], "Google Ads", "Conversion measurement for campaigns."));
  }
  if (has("metaPixelId")) {
    marketingServices.push(service("meta_pixel", ["marketing"], [/^_fbp$/, /^fr$/], "Meta Pixel", "Campaign measurement on Facebook and Instagram."));
  }
  if (has("linkedinPartnerId")) {
    marketingServices.push(service("linkedin", ["marketing"], [/^li_sugr$/, /^UserMatchHistory$/], "LinkedIn Insight", "Campaign measurement on LinkedIn."));
  }
  if (has("microsoftUetTagId")) {
    marketingServices.push(service("microsoft_ads", ["marketing"], [/^_uetvid$/], "Microsoft Ads (UET)", "Conversion measurement for Bing campaigns."));
  }
  if (has("tiktokPixelId")) {
    marketingServices.push(service("tiktok", ["marketing"], [/^_ttp$/], "TikTok Pixel", "Campaign measurement on TikTok."));
  }
  if (has("pinterestTagId")) {
    marketingServices.push(service("pinterest", ["marketing"], [/^_pin_.*$/], "Pinterest Tag", "Campaign measurement on Pinterest."));
  }
  if (has("xPixelId")) {
    marketingServices.push(service("x_pixel", ["marketing"], [/^_twclid$/], "X Pixel", "Campaign measurement on X."));
  }

  var externalServices = [];
  if (server.calcom && server.calcom.enabled) {
    externalServices.push(service("calcom", ["external"], [], "Cal.com", "Booking calendar embed."));
  }
  if (server.stripe && server.stripe.enabled) {
    externalServices.push(service("stripe", ["external"], [/^__stripe_mid$/], "Stripe", "Payment processing."));
  }

  window.klaroConfig = {
    version: 2,
    elementID: "klaro",
    storageMethod: "cookie",
    storageName: server.storageName || "skeleton_consent",
    cookieExpiresAfterDays: 365,
    default: false,
    mustConsent: false,
    acceptAll: true,
    hideDeclineAll: false,
    htmlTexts: true,
    noAutoLoad: true,
    translations: {
      en: {
        consentNotice: {
          description: "We use cookies for essential features and, only with your consent, for statistics and marketing.",
          learnMore: "Choose individually",
        },
        consentModal: {
          title: "Cookie settings",
          description: "Decide which categories you allow. Essential cookies are always on because the site cannot work without them.",
        },
        purposes: {
          essential: { title: "Essential", description: "Required for the site to function." },
          analytics: { title: "Statistics", description: "Help us understand how the site is used." },
          marketing: { title: "Marketing", description: "Measure campaign success." },
          external: { title: "External content", description: "Embed third-party features on request." },
        },
        privacyPolicy: { name: "privacy policy", text: "Read the {privacyPolicy} to learn more." },
      },
    },
    services: [
      service("essential", ["essential"], [/^csrftoken$/, /^sessionid$/, /^skeleton_consent$/], "Essential", "Session and security cookies.")
    ]
      .concat(analyticsServices)
      .concat(marketingServices)
      .concat(externalServices),
    callback: function (consent, app) {
      if (!app) {
        Object.keys(consent).forEach(function (key) {
          if (consent[key]) fireService(key);
        });
        announce(consent);
        return;
      }
      if (consent[app.name]) fireService(app.name);
      announce(consent);
    },
  };

  function fireService(name) {
    if (LOADERS[name]) {
      try {
        LOADERS[name]();
      } catch (e) {
        /* a broken tracker must never break the page */
      }
    }
  }

  function announce(consent) {
    var klaro = window.klaro;
    var prefs = summarize(consent, klaro);
    window.getConsentPrefs = function () {
      return summarize(klaro ? klaro.getManager().consents : {}, klaro);
    };
    window.hasServiceConsent = function (name) {
      if (!window.klaro) return false;
      return !!window.klaro.getManager().consents[name];
    };
    window.handleConsent = function (decision, options) {
      var manager = window.klaro && window.klaro.getManager();
      if (!manager) return;
      if (decision === "all") {
        manager.acceptAll();
      } else if (decision === "none") {
        manager.declineAll();
      } else if (decision === "merge") {
        (options && options.services ? options.services : []).forEach(function (name) {
          manager.consents[name] = true;
        });
        manager.saveAndApplyConsents();
      }
    };
    window.openCookieModal = function () {
      if (window.klaro && typeof window.klaro.show === "function") window.klaro.show();
    };
    document.dispatchEvent(new CustomEvent("skeleton:consent", { detail: prefs }));
  }

  function summarize(consents, klaro) {
    var manager = klaro ? klaro.getManager() : null;
    var services = manager ? manager.services : [];
    var purposes = { essential: true, analytics: false, marketing: false, external: false };
    var byService = {};
    services.forEach(function (svc) {
      var on = !!consents[svc.name];
      byService[svc.name] = on;
      svc.purposes.forEach(function (purpose) {
        if (on && purposes.hasOwnProperty(purpose)) purposes[purpose] = true;
      });
    });
    purposes.essential = true;
    return {
      essential: true,
      analytics: purposes.analytics,
      marketing: purposes.marketing,
      external: purposes.external,
      services: byService,
    };
  }

  if (googleOn) consentModeDefaults();

  document.addEventListener("click", function (event) {
    var opener = event.target.closest("[data-open-cookie-settings]");
    if (!opener) return;
    event.preventDefault();
    if (window.klaro && window.klaro.show) {
      window.klaro.show();
    }
  });
})();
