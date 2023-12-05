import datetime
import numpy as np

from matplotlib import pyplot as plt

#import astropy
from astropy import units as u
from astropy.time import Time
from astropy.coordinates import EarthLocation, AltAz, get_sun, get_moon
from astropy import constants

def array(val):
    val = np.array(val)
    if val.shape == ():
        val.shape = (1,)
    return val

def conform(arr_0,arr_1):
    """
    Conform arr_0 to arr_1.
    """
    if arr_0.shape != arr_1.shape:
        arr_0 = np.ones(arr_1.shape)*arr_0[0]
    return arr_0

def raw_area(R,r,d):
    """
    Calculate the area of intersecting circles with radii R
    and r and separation d, but do not account for zero intersection,
    annular eclipse, moon is larger than the sun.

    R = r_sun
    r = r_moon
    """

    A = ( r**2 * np.arccos( (d**2 + r**2 - R**2)/(2*d*r))
        + R**2 * np.arccos( (d**2 + R**2 - r**2)/(2*d*R))
        - 0.5 * np.sqrt((-d+r+R)*(d+r-R)*(d-r+R)*(d+r+R))
        )

    return A

def area_intersect(r_sun,r_moon,d):
    """
    Calculate the area of intersecting circles with radii R
    and r and separation d.

    Reference:
    Weisstein, Eric W. "Circle-Circle Intersection."
        From MathWorld--A Wolfram Web Resource.
        http://mathworld.wolfram.com/Circle-CircleIntersection.html
    """

    r_sun   = array(r_sun)
    r_moon  = array(r_moon)
    d       = array(d)

    intersect = d <= r_sun + r_moon
    inset     = d <= np.abs(r_sun-r_moon)

    A       = np.empty(r_sun.shape)
    A[:]    = np.nan
    
    tf_none         = np.logical_not(intersect)
    A[tf_none]      = 0.

    # Compute area when the sun is bigger than the moon. (Annular eclipse.)
    tf_annular      = np.logical_and(inset,r_sun > r_moon)
    A[tf_annular]   = np.pi*r_sun[tf_annular]**2 - (np.pi*r_sun[tf_annular]**2 - np.pi*r_moon[tf_annular]**2)

    # Compute area when the moon is bigger than the sun.
    tf_total        = np.logical_and(inset,r_sun <= r_moon)
    A[tf_total]     = np.pi*r_moon[tf_total]**2

    # Compute area for the partial eclipses.
    tf              = np.logical_not(np.logical_or.reduce((tf_none,tf_annular,tf_total)))
    A[tf]           = raw_area(r_sun[tf],r_moon[tf],d[tf])

    return A

def apparent_size(R, distance):
        return (R/distance).to(u.arcmin, u.dimensionless_angles())

def calculate_obscuration(date_time,lat=None,lon=None,height=0.,loc=None,return_dict=False,
        min_solar_elev_deg=0,plot_obscuration=None):
    """
    date_time:   datetime.datetime object
    lat:         degrees +N / -S
    lon:         degrees +E / -W
    height:      meters
    loc:         AstroPy EarthLocation object. If provided, this is used instead of lon, lat, and height.
    return_dict:        If True, return a dictionary with more data than just obscuration values.
    min_solar_elev_deg: Minimum solar elevation in degrees to report an obscuration value greater than 0.
                        This is used to prevent eclipses from being predicted on the nightside of the Earth.
    plot_obscuration:   Filename/path to save an image of the plot showing the computed obscuration geometry.
                        Images will only be produced for single location inputs (not vectors/arrays).
                        If None, no image is saved.

    returns:    Eclipse obscuration (solar disk area obscured / solar disk area).
                Obscuration will be 0 if below the horizon.
    """
    date_time   = array(date_time)
    lat         = array(lat)
    lon         = array(lon)
    height      = array(height)

    lat         = conform(lat,date_time)
    lon         = conform(lon,date_time)
    height      = conform(height,date_time)

    R_sun   = constants.R_sun
    R_moon  = 1737.1 * u.km

    if loc is None:
        loc     = EarthLocation.from_geodetic(lon,lat,height)

    time_aa     = Time(date_time)
    aaframe     = AltAz(obstime=time_aa, location=loc)

    sun_aa      = get_sun(time_aa).transform_to(aaframe)
    moon_aa     = get_moon(time_aa).transform_to(aaframe)
    sep         = sun_aa.separation(moon_aa)

    sunsize     = apparent_size(R_sun, sun_aa.distance)
    moonsize    = apparent_size(R_moon, moon_aa.distance)

    r_sun_deg   = sunsize.to(u.degree).value
    r_moon_deg  = moonsize.to(u.degree).value
    sep_deg     = sep.degree

    A   = area_intersect(r_sun_deg,r_moon_deg,sep_deg)
    obs = A/(np.pi*r_sun_deg**2)

    tf      = sun_aa.alt.value < min_solar_elev_deg
    obs[tf] = 0

    if (plot_obscuration is not None) and (len(lat) == 1):
        # Code to plot the obscuration.
        # From https://gist.github.com/eteq/f879c2fe69d75d1c5a9e007b0adce30d
        sun_circle  = plt.Circle((sun_aa.az.deg, sun_aa.alt.deg), 
                    sunsize.to(u.deg).value,
                    fc='yellow')
        moon_circle = plt.Circle((moon_aa.az.deg, moon_aa.alt.deg), 
                     moonsize.to(u.deg).value,
                     fc='black', alpha=.5)

        ax = plt.subplot(aspect=1)
        ax.add_patch(sun_circle)
        ax.add_patch(moon_circle)
        biggest = max(sep.deg, sunsize.to(u.deg).value, moonsize.to(u.deg).value)
        plt.xlim(sun_aa.az.deg-biggest*1.2, sun_aa.az.deg+biggest*1.2)
        plt.ylim(sun_aa.alt.deg-biggest*1.2, sun_aa.alt.deg+biggest*1.2)

        plt.xlabel('Azimuth')
        plt.ylabel('Altitude');

        title = []
        txt = 'Lat: {:0.2f}\N{DEGREE SIGN} Lon: {:0.2f}\N{DEGREE SIGN} Height: {!s} km'.format(lat[0],lon[0],height[0]/1000.)
        title.append(txt)
        txt = 'Obsc: {:0.3f} Sun-Moon Sep: {:0.4f}\N{DEGREE SIGN} Solar Elevation: {:0.1f}\N{DEGREE SIGN}'.format(float(obs),float(sep_deg),float(sun_aa.alt.value))
        title.append(txt)
        plt.title('\n'.join(title))
        plt.savefig(plot_obscuration,bbox_inches='tight')

    if len(obs) == 1:
        obs = float(obs)

    if return_dict:
        return {'obsc':obs,'sun_moon_sep_deg':sep_deg,'solar_elev_deg':sun_aa.alt.value}
    else:
        return obs

if __name__ == '__main__':
    # http://xjubier.free.fr/en/site_pages/solar_eclipses/ASE_2023_GoogleMapFull.html
    # Anular Eclipse - Data (Oct, 14th 2023)
    lat =  37.5426
    lon = -122.1111
    date_time   = datetime.datetime(2023,10,14,12,13,00)
    obs         = calculate_obscuration(date_time,lat,lon)
    print('Sound Around Town ({!s}, {!s})'.format(lat,lon))
    print('   Eclipse Max: {!s}'.format(date_time))
    print('   Astropy Calculated Obscuration: {!s}'.format(obs))
    print('')

    date_time   = datetime.datetime(2023,10,14,12)
    obs         = calculate_obscuration(date_time,lat,lon)
    print('   No Eclipse: {!s}'.format(date_time))
    print('   Astropy Calculated Obscuration: {!s}'.format(obs))
    print('')


    # Test vectorized version of code.
    sDate   = datetime.datetime(2023,10,14,12)
    eDate   = datetime.datetime(2023,10,14,12)
    dates   = [sDate]
    while dates[-1] < eDate:
        new_date    = dates[-1] + datetime.timedelta(minutes=2)
        dates.append(new_date)

    lat     =  37.5426
    lon     = -122.1111
    dates   = np.array(dates)

    obs     = calculate_obscuration(dates,lat,lon,height=3e5)
    print(obs)
