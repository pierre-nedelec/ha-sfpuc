# 🚰 SFPUC Water Usage for Home Assistant

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)
[![HACS][hacs-shield]][hacs]
[![Project Maintenance][maintenance-shield]](https://github.com/pierre-nedelec)

**Monitor your San Francisco water usage directly in Home Assistant!**

This custom integration automatically fetches hourly water usage data from the San Francisco Public Utilities Commission (SFPUC) and integrates it seamlessly into your Home Assistant dashboard and statistics.

## ✨ Features

- 📊 **Hourly Water Usage Monitoring** - Track your water consumption with hourly granularity
- 📈 **Home Assistant Statistics** - Full integration with HA's long-term statistics system
- 🔄 **Automatic Updates** - Fetches new data every 4 hours automatically
- 🏠 **Dashboard Integration** - Use water usage data in dashboards, automations, and notifications
- 📱 **Mobile Ready** - Access your water usage data from anywhere
- 🔐 **Secure** - Uses your existing SFPUC account credentials

## 🚀 Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the "+" button in the bottom right
4. Search for "SFPUC Water Usage"
5. Click "Install"
6. Restart Home Assistant

### Manual Installation

1. Download the `sfpuc` folder from this repository
2. Copy it to your `custom_components` directory
3. Restart Home Assistant

## ⚙️ Configuration

### Step 1: Add Integration
1. Go to **Settings** → **Devices & Services** → **Integrations**
2. Click **"+ Add Integration"**
3. Search for **"SFPUC Water Usage"**
4. Click on the integration

### Step 2: Enter Credentials
- **Username**: Your SFPUC account username
- **Password**: Your SFPUC account password

> 🔒 **Privacy Note**: Credentials are stored securely in Home Assistant's encrypted storage

### Step 3: Start Monitoring
The integration will automatically:
- Fetch historical data (up to 90 days)
- Continue monitoring every 4 hours
- Store data in Home Assistant statistics

## 📊 Using Your Data

### Energy Dashboard
Add water usage to your Energy dashboard:
1. Go to **Settings** → **Dashboards** → **Energy**
2. Add **"SFPUC Water Usage"** as a water source

### Automations
Create automations based on water usage:
```yaml
automation:
  - alias: "High Water Usage Alert"
    trigger:
      platform: numeric_state
      entity_id: sensor.sfpuc_water_usage
      above: 50  # gallons per hour
    action:
      service: notify.mobile_app
      data:
        message: "High water usage detected: {{ states('sensor.sfpuc_water_usage') }} gallons/hour"
```

### Dashboard Cards
Display water usage in your dashboard:
```yaml
type: statistics-graph
entities:
  - sensor.sfpuc_water_usage
title: Daily Water Usage
days_to_show: 30
```

## 🔧 Troubleshooting

### Integration Not Fetching Data
- Check your SFPUC credentials are correct
- Ensure SFPUC website is accessible
- Check Home Assistant logs for errors

### Negative Water Usage Values
- This has been fixed in recent versions
- Delete and re-add the integration if still experiencing issues

### Missing Historical Data
- The integration fetches up to 90 days of historical data
- SFPUC only provides limited historical data

## 🏗️ Development

### Contributing
Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

### Local Development
```bash
# Clone the repository
git clone https://github.com/pierre-nedelec/ha-sfpuc.git
cd ha-sfpuc

# Install in development mode
pip install -e .
```

## 📝 Changelog

### v0.1.0
- Initial release
- Basic water usage monitoring
- SFPUC website integration

## 🆘 Support

- 🐛 **Bug Reports**: [GitHub Issues](https://github.com/pierre-nedelec/ha-sfpuc/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/pierre-nedelec/ha-sfpuc/discussions)
- 📧 **Email**: [Contact Developer](mailto:your-email@example.com)

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Thanks to the Home Assistant community
- San Francisco Public Utilities Commission for providing the data
- All contributors and users who help improve this integration

---

**⭐ If you like this integration, please give it a star on GitHub! ⭐**

[releases-shield]: https://img.shields.io/github/release/pierre-nedelec/ha-sfpuc.svg?style=for-the-badge
[releases]: https://github.com/pierre-nedelec/ha-sfpuc/releases
[commits-shield]: https://img.shields.io/github/commit-activity/y/pierre-nedelec/ha-sfpuc.svg?style=for-the-badge
[commits]: https://github.com/pierre-nedelec/ha-sfpuc/commits/main
[license-shield]: https://img.shields.io/github/license/pierre-nedelec/ha-sfpuc.svg?style=for-the-badge
[hacs-shield]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge
[hacs]: https://github.com/hacs/integration
[maintenance-shield]: https://img.shields.io/badge/maintainer-Pierre%20Nedelec-blue.svg?style=for-the-badge
