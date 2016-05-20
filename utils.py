import numpy as np
from scipy.interpolate import interp1d

def compute_cdf(data):

    data_size=len(data)

    # Set bins edges
    data_set=sorted(set(data))
    bins=np.append(data_set, data_set[-1]+1)

    # Use the histogram function to bin the data
    counts, bin_edges = np.histogram(data, bins=bins, density=False)

    counts=counts.astype(float)/data_size

    # Find the cdf
    cdf_samples = np.cumsum(counts)

    cdf = interp1d(bin_edges[0:-1], cdf_samples)
    
    inverse_cdf = interp1d(cdf_samples,bin_edges[0:-1])

    return cdf, inverse_cdf, cdf_samples

'''
Find the minimum values that is not zero.
Returns 0 if values are all zero
'''
def find_non_zero_min(values):
    
    min = values[0]
    
    for x in values[1:]:
        
        if (x!=0 and (min==0 or x < min)):
            min = x
        
    return min
