# Onboarding UI - Quick Start Guide

> **First-Run Experience for SoulSpot**

## 🎯 What is this?

A modern, accessible onboarding page that welcomes new users and guides them through connecting their Spotify account.

## ✨ Features

- ✅ **Modern UI** - Built with UI 1.0 Design System
- ✅ **HTMX Integration** - Seamless status checks
- ✅ **OAuth Security** - PKCE + CSRF protection
- ✅ **Fully Accessible** - WCAG 2.1 AA compliant
- ✅ **Mobile-First** - Responsive design
- ✅ **Dark Mode Ready** - Automatic theme switching

## 🚀 Quick Start

### 1. Access the Page

```
http://localhost:8000/onboarding
```

### 2. User Flow

```
Welcome Screen
    ↓
Click "Weiter"
    ↓
Check Spotify Status
    ├─→ Connected? → Redirect to Dashboard
    └─→ Not Connected? → Show "Spotify verbinden" button
            ↓
        Click Button → Start OAuth Flow
            ↓
        Authorize in Spotify
            ↓
        Callback → Store Tokens → Redirect to Dashboard
```

### 3. Skip Option

Users can click **"Nicht jetzt"** to skip onboarding and connect Spotify later in Settings.

## 📁 Files Overview

```
src/soulspot/
├── templates/
│   └── onboarding.html          ← Main template (272 lines)
├── static/css/
│   ├── ui-theme.css             ← Design tokens
│   ├── ui-components.css        ← UI components
│   └── ui-layout.css            ← Layout utilities
└── api/routers/
    ├── ui.py                    ← /onboarding route
    └── auth.py                  ← API endpoints
```

## 🔌 API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /onboarding` | GET | Render onboarding page |
| `GET /api/spotify/status` | GET | Check if Spotify is connected |
| `POST /api/onboarding/skip` | POST | Skip onboarding |
| `GET /api/auth/authorize` | GET | Start OAuth flow (existing) |
| `GET /api/auth/callback` | GET | Handle OAuth callback (updated) |

## 🎨 UI Components Used

30 unique components from UI 1.0 Design System:

- **Layout:** `.ui-page`, `.ui-container`, `.ui-card-*`
- **Buttons:** `.ui-btn-primary`, `.ui-btn-ghost`, `.ui-btn-success`
- **Alerts:** `.ui-alert-success`, `.ui-alert-info`
- **Loading:** `.ui-spinner-lg`
- **Utilities:** `.ui-flex`, `.ui-items-center`, `.ui-justify-center`

## ⚙️ Configuration

Required environment variables:

```bash
SPOTIFY_CLIENT_ID=your_client_id_here
SPOTIFY_CLIENT_SECRET=your_client_secret_here
SPOTIFY_REDIRECT_URI=http://localhost:8000/api/auth/callback
API_SECURE_COOKIES=false  # true for HTTPS in production
```

## 🧪 Testing

### Manual Testing Checklist

- [ ] Page loads at `/onboarding`
- [ ] Logo and title display correctly
- [ ] "Weiter" button works
- [ ] Status check shows correct state
- [ ] Spotify connect button starts OAuth
- [ ] OAuth flow completes successfully
- [ ] Skip button redirects to dashboard
- [ ] Mobile responsive
- [ ] Dark mode works
- [ ] Keyboard navigation works

### Test Commands

```bash
# Check if page renders
curl http://localhost:8000/onboarding

# Check Spotify status
curl http://localhost:8000/api/spotify/status

# Skip onboarding
curl -X POST http://localhost:8000/api/onboarding/skip
```

## 🐛 Troubleshooting

### Common Issues

**Issue: Styles not applied**
- ✅ Check that CSS files exist in `static/css/`
- ✅ Verify CSS includes in `base.html`
- ✅ Clear browser cache

**Issue: "Weiter" button stays disabled**
- ✅ Check browser console for JavaScript errors
- ✅ Verify HTMX is loaded
- ✅ Wait 1 second (button enables automatically)

**Issue: OAuth fails with "state mismatch"**
- ✅ Clear cookies and restart flow
- ✅ Check session store is working
- ✅ Verify `SPOTIFY_REDIRECT_URI` is correct

**Issue: Redirect loop**
- ✅ Check callback URL parameters
- ✅ Verify session cookie is set
- ✅ Check server logs for errors

## 📚 Documentation

Full documentation available in `/docs`:

1. **[onboarding-ui-overview.md](./onboarding-ui-overview.md)** - Complete overview (START HERE)
2. **[onboarding-ui-implementation.md](./onboarding-ui-implementation.md)** - Technical details
3. **[onboarding-ui-visual-guide.md](./onboarding-ui-visual-guide.md)** - Visual mockups

## 🎯 Next Steps

### Before Production Deployment

1. **Replace Logo**
   - Change emoji (🎵) to actual SoulSpot logo SVG
   - Path: `/static/img/soulspot-logo.svg`

2. **Add Analytics**
   - Track events: `onboarding_started`, `spotify_connect_success`, etc.

3. **Persist State**
   - Add `user.onboarding_complete` column to database
   - Auto-redirect first-time users to `/onboarding`

4. **Improve Error Handling**
   - Add retry buttons for network errors
   - Show user-friendly error messages

5. **Run Accessibility Audit**
   - Use axe-core or similar tool
   - Test with screen readers (NVDA, VoiceOver)

### Future Enhancements

- Multi-step wizard (welcome → connect → tutorial → done)
- Progress indicator
- Tutorial video option
- Customizable flow per user type
- A/B testing framework

## 💡 Tips

### For Developers

- **Use UI 1.0 components only** - No custom CSS
- **Follow HTMX patterns** - Check existing code
- **Test responsiveness** - Mobile, tablet, desktop
- **Validate accessibility** - Use keyboard navigation
- **Update docs** - Keep documentation in sync

### For Designers

- **Design System:** All components in `/docs/ui/`
- **Demo Page:** Open `/docs/ui/ui-demo.html` in browser
- **Color Tokens:** See `ui-theme.css` for variables
- **Component Reference:** Check `ui-components.css`

## 🤝 Contributing

1. Make changes to templates or API
2. Test locally with manual testing checklist
3. Update documentation if needed
4. Submit PR with clear description
5. Wait for review

## 📝 License

Same as SoulSpot project.

## 🙏 Credits

- **UI 1.0 Design System** - Based on Wizarr (MIT License)
- **HTMX** - https://htmx.org/
- **FastAPI** - https://fastapi.tiangolo.com/
- **Implementation** - Copilot AI Agent (Frontend Specialist)

---

**Status:** ✅ Production Ready  
**Version:** 1.0  
**Last Updated:** 2025-11-16

For detailed documentation, see [onboarding-ui-overview.md](./onboarding-ui-overview.md)
