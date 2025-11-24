"""
Schema definition for BMW technical data extraction.

This defines what data points we want to extract from each technical data page.
ALL VALUES ARE STRINGS to preserve ranges like "20-30" and avoid parsing errors.
"""

TECHNICAL_DATA_SCHEMA = {
    "vehicle_identification": {
        "brand": "string",
        "model": "string",
        "variant": "string",
        "model_year": "string",
        "model_code": "string"
    },
    "combustion_engine": {
        "engine_type": "string",  # TwinPower Turbo, etc.
        "power_kw": "string",  # e.g., "140"
        "power_hp": "string",  # e.g., "190"
        "power_rpm": "string",  # RPM range e.g., "4.400 - 6.500"
        "torque_nm": "string",
        "torque_rpm": "string",  # RPM at max torque
        "displacement_cc": "string",
        "cylinders": "string",
        "fuel_type": "string"
    },
    "electric_motor": {
        "motor_type": "string",
        "power_nominal_kw": "string",  # Nominal power
        "power_30min_kw": "string",  # 30-minute power rating
        "power_combined": "string",  # Combined format like "135/184"
        "torque_nm": "string",  # Electric motor torque
        "motor_count": "string"  # Number of motors
    },
    "system_performance": {
        "total_power_kw": "string",  # Combined system power
        "total_power_hp": "string",
        "total_torque_nm": "string"
    },
    "electric_drive": {
        "battery_capacity_kwh": "string",
        "battery_capacity_gross_kwh": "string",
        "battery_capacity_net_kwh": "string",
        "battery_type": "string",
        "battery_voltage_v": "string",
        "electric_range_km": "string",
        "electric_range_wltp_km": "string",
        "electric_range_wltp_min_km": "string",
        "electric_range_wltp_max_km": "string",
        "charging_time_ac_hours": "string",
        "charging_time_dc_minutes": "string",
        "charging_power_ac_kw": "string",
        "charging_power_dc_kw": "string",
        "charging_power_max_kw": "string"
    },
    "performance": {
        "acceleration_0_100_kmh_seconds": "string",
        "top_speed_kmh": "string",
        "top_speed_limited": "string",
        "acceleration_80_120_kmh_seconds": "string"
    },
    "fuel_consumption": {
        "consumption_combined_l_100km": "string",
        "consumption_urban_l_100km": "string",
        "consumption_extra_urban_l_100km": "string",
        "consumption_wltp_l_100km": "string",
        "co2_emissions_combined_g_km": "string",
        "co2_emissions_wltp_g_km": "string",
        "co2_class": "string",  # e.g., "B", "C", etc.
        "emission_class": "string",  # Euro 6d, etc.
        "efficiency_class": "string"
    },
    "electric_consumption": {
        "consumption_wltp_kwh_100km": "string",
        "consumption_combined_kwh_100km": "string",
        "consumption_min_kwh_100km": "string",
        "consumption_max_kwh_100km": "string",
        "co2_emissions_g_km": "string",
        "co2_class": "string"
    },
    "noise_emissions": {
        "pass_by_noise_db": "string",  # Vorbeifahrtgeräusch
        "standstill_noise_db": "string",  # Standgeräusch
        "standstill_noise_rpm": "string"  # RPM at measurement
    },
    "sustainability": {
        "vehicle_footprint_co2e_tons": "string",  # CO2e at delivery (Scope 1,2,3)
        "secondary_material_quota_percent": "string",  # Recycled materials %
        "recyclability_percent": "string",
        "recovery_rate_percent": "string"
    },
    "dimensions": {
        "length_mm": "string",
        "width_mm": "string",
        "width_with_mirrors_mm": "string",
        "width_with_mirrors_driver_side_mm": "string",
        "width_with_mirrors_passenger_side_mm": "string",
        "height_mm": "string",
        "wheelbase_mm": "string",
        "ground_clearance_mm": "string",
        "track_width_front_mm": "string",
        "track_width_rear_mm": "string",
        "overhang_front_mm": "string",
        "overhang_rear_mm": "string"
    },
    "weight": {
        "curb_weight_kg": "string",
        "curb_weight_min_kg": "string",
        "curb_weight_max_kg": "string",
        "gross_weight_kg": "string",
        "payload_kg": "string",
        "max_roof_load_kg": "string",
        "max_trailer_weight_braked_kg": "string",
        "max_trailer_weight_unbraked_kg": "string",
        "max_towbar_load_kg": "string",
        "axle_load_front_kg": "string",
        "axle_load_rear_kg": "string"
    },
    "capacity": {
        "fuel_tank_liters": "string",
        "luggage_capacity_liters": "string",
        "luggage_capacity_seats_down_liters": "string",
        "seating_capacity": "string",
        "luggage_capacity_min_liters": "string",
        "luggage_capacity_max_liters": "string"
    },
    "transmission": {
        "transmission_type": "string",  # Automatic, Manual
        "gears": "string",
        "drive_type": "string"  # FWD, RWD, AWD, 4WD, xDrive
    },
    "wheels_tires": {
        "tire_size_front": "string",
        "tire_size_rear": "string",
        "wheel_size_front_inches": "string",
        "wheel_size_rear_inches": "string",
        "rim_width_front": "string",
        "rim_width_rear": "string"
    },
    "pricing": {
        "base_price_eur": "string",
        "price_as_shown_eur": "string"
    }
}

EXTRACTION_INSTRUCTIONS = """
Extract technical specifications from this vehicle page.

⚠️ FIRST: VALIDATE THE PAGE SOURCE
Before extracting, determine if this page contains actual technical specifications:
- "yes" = Page has comprehensive technical data (power, consumption, dimensions, etc.)
- "maybe" = Page has some technical data but incomplete (might be overview/summary page)
- "no" = Page does NOT contain technical specifications (configurator, news, accessories, dealer page, etc.)

⚠️ CRITICAL RULES - NO EXCEPTIONS:
1. Extract EVERY SINGLE NUMBER you find on the page - leave NOTHING behind
2. ALL VALUES MUST BE STRINGS (including numbers) - preserve ranges like "20-30"
3. If you see a number with units, extract it exactly as shown
4. For power/torque with RPM: extract both the value AND the RPM range separately
5. For dual values (like "135/184"): keep them together in one field
6. For ranges (like "10 - 16,8"): preserve the exact format with spaces and commas
7. Extract noise measurements (dB), CO2e footprint, recycling percentages
8. If a field is truly not present, set it to null - but look VERY carefully first
9. For hybrid vehicles: separate combustion engine data from electric motor data
10. Look for sustainability data: CO2e footprint, secondary materials, recyclability

DATA POINTS TO EXTRACT (extract ALL of these if present):

COMBUSTION ENGINE:
- Engine type (TwinPower Turbo, etc.)
- Power in kW and HP
- RPM range for power (e.g., "4.400 - 6.500")
- Torque in Nm
- RPM at max torque
- Displacement, cylinders, fuel type

ELECTRIC MOTOR:
- Motor type
- Nominal power (Nennleistung)
- 30-minute power rating
- Combined power format (e.g., "135/184")
- Torque in Nm
- Number of motors

SYSTEM PERFORMANCE (for hybrids):
- Total system power (kW and HP)
- Total system torque

BATTERY & RANGE:
- Battery capacity (gross and net)
- Electric range WLTP (include min-max ranges)
- Charging times and power (AC and DC)

CONSUMPTION & EMISSIONS:
- Fuel consumption (combined, urban, extra-urban, WLTP)
- Electric consumption with ranges (e.g., "10 - 16,8")
- CO2 emissions in g/km
- CO2 CLASS (e.g., "B", "C") - this is different from emission class!
- Emission class (Euro 6d, etc.)
- Efficiency class

NOISE:
- Pass-by noise (Vorbeifahrtgeräusch) in dB
- Standstill noise (Standgeräusch) in dB
- RPM at standstill noise measurement

SUSTAINABILITY:
- Vehicle footprint CO2e at delivery (Scope 1, 2, 3up) in tons
- Secondary material quota (recycled materials) in %
- Recyclability %
- Recovery rate %

DIMENSIONS:
- Length, width, height, wheelbase
- Width with mirrors (total and separate for driver/passenger side)
- Track width front/rear
- Overhangs

WEIGHT:
- Curb weight (Leergewicht) - include ranges if given
- Gross weight, payload
- Axle loads
- Towing capacities

CAPACITY:
- Fuel tank, luggage capacity (normal and seats down)

TRANSMISSION & DRIVETRAIN:
- Type, gears, drive type (xDrive, etc.)

WHEELS & TIRES:
- Tire sizes front/rear
- Wheel sizes in inches
- Rim widths

PRICING:
- Base price, configured price

⚠️ REMEMBER: If you see a number on the page, EXTRACT IT! Don't skip anything!

Return the data as a JSON object with ALL VALUES AS STRINGS.
"""

def get_extraction_prompt(url: str, html_content: str) -> str:
    """Generate the extraction prompt for Claude."""
    return f"""Extract technical specifications from this vehicle page.

URL: {url}

{EXTRACTION_INSTRUCTIONS}

Page content:
{html_content[:30000]}

Return ONLY valid JSON following this structure:
{{
    "valid_source": "yes|maybe|no",
    "url": "{url}",
    "vehicle_identification": {{...}},
    "combustion_engine": {{...}},
    "electric_motor": {{...}},
    "system_performance": {{...}},
    "electric_drive": {{...}},
    "performance": {{...}},
    "fuel_consumption": {{...}},
    "electric_consumption": {{...}},
    "noise_emissions": {{...}},
    "sustainability": {{...}},
    "dimensions": {{...}},
    "weight": {{...}},
    "capacity": {{...}},
    "transmission": {{...}},
    "wheels_tires": {{...}},
    "pricing": {{...}}
}}

⚠️ CRITICAL INSTRUCTIONS:
1. Set "valid_source" to "yes", "maybe", or "no" based on page content
2. If "no", you can set all other fields to null
3. If "yes" or "maybe", extract EVERY number you see!
4. ALL values must be strings, including numbers and ranges
"""
