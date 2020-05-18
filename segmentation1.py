import warnings
warnings.simplefilter("ignore", DeprecationWarning)

from segmentation2 import *
import keras
from utility_functions import *
import time

#### Loading weights ####
mFile = 'segmentation_data/weights_30_30_.h5'
model = keras.models.load_model(mFile)
rm_detail = open('log.txt', 'a')

#### OTSU Threshold ####
def otsu_threshold(gray):
    h,w = gray.shape
    count = {i:0 for i in range(256)}
    for i in range(h):
        for j in range(w):
            count[gray[i,j]] += 1
    prob = np.array([count[i]/float(h*w) for i in sorted(count)])
    means = np.array([prob[i]*(i+1) for i in count])
    mean = np.sum(means)
    minvar = -np.inf
    minT = 0
    for t in range(256):
        w1 = np.sum([i for i in prob[:t+1]])
        w2 = 1.0-w1
        if not w1 or not w2: continue
        m1 = np.sum([i for i in means[:t+1]])
        mean1 = m1/w1
        mean2 = (mean - m1)/w2
        bcvar = w1*w2*(mean2-mean1)**2
        if bcvar > minvar:
            minvar = bcvar
            minT = t
    return minT

#### Function to get the value of image in given Range ####
def get_img_value_inRange(img, mask, sindex, s):
    return np.array([[img[i, j] if mask[i, j] == sindex else [0, 0, 0] for j in range(s[2], s[3])] for i in range(s[0], s[1])], dtype=np.uint8)

#### Function to Remove Mask ####
def remove_mask(mask, val, mrange):
    mask[mrange[0]:mrange[1], mrange[2]:mrange[3]] = [[0 if pixel == val else pixel for pixel in row] for row in mask[mrange[0]:mrange[1], mrange[2]:mrange[3]]]
    return mask

#### Function to check if More Grain are in Image ####
def isMoregrain(iimg, T):
    iimg = generate_newcolorimg_by_padding(iimg, 30, 30)[:, :, 2]
    gray = np.array([[1 if pixel >= T else 0 for pixel in row] for row in iimg], dtype=np.uint8)
    boundry = np.array([get_boundry_img_matrix(gray, 1).reshape(30, 30, 1)], dtype=np.float32)
    return 1 if np.argmax(model.predict(boundry)) == 0 else 0

#### Function to Segment Grain ####
def segment_image(img_file, dlog=0):
    t0 = time.time()
    org = cv2.imread(img_file, cv2.IMREAD_COLOR)
    h, w = org.shape[:2]

    img=org.copy()
    
    img = cv2.fastNlMeansDenoisingColored(img,None,10,10,7,21)
    
    gray = np.array([[pixel[2] for pixel in row]for row in img])

    #### threshold value by using otsu thresholding ####
    T = otsu_threshold(gray=gray)

    #### threshold image ####
    thresh = np.array([[0 if pixel<T else 255 for pixel in row]for row in gray], dtype=np.uint8)

    #### Level 1 segmentation ####

    mask = get_8connected_v2(thresh, mcount=5)

    s = cal_segment_area(mask)

    low_Tarea, up_Tarea = areaThreshold_by_havg(s, 3)
    slist = list(s)
    s1count = total = 0
    total += len(slist)
    for i in slist:
        area = (s[i][0] - s[i][1]) * (s[i][2] - s[i][3])
        if area < low_Tarea:# or area > up_Tarea:
            rm = s.pop(i)
            s1count += 1
            
    if dlog == 1: rm_detail.write("\n\t%d Number of segment rejected out of %d in L1 segmentation\n"%(s1count, total))

    #### Level 2 segmentation ####
    new_s = {}

    s_range = [i for i in s]
    max_index = max(s_range)

    segments = {}
    s2count = extra = 0
    
    for sindex in s_range:
        s1 = {}
        org1 = get_img_value_inRange(org, mask, sindex, s[sindex])
        iimg = get_img_value_inRange(img, mask, sindex, s[sindex])
        if len(iimg) == 0:
            continue

        if isMoregrain(iimg, T):
            a = segmentation_2(iimg, T=T, index=max_index + 5 + len(new_s))
        else:
            segments[sindex] = org1
            continue
        if not a:
            segments[sindex] = org1
            extra += 1
            continue
        masks, trm = a
        s2count += trm
        total += len(masks) + trm -1
        for msk in masks:
            a = cal_segment_area(msk)
            s1.update(a)
            for ii in a:
                segments[ii] = get_img_value_inRange(org1, msk, ii, s1[ii])

        #### segmenting adding ####
        m = s.pop(sindex)
        mask =remove_mask(mask, sindex, m)
        mask1 = np.sum(masks, axis=0)
        mask[m[0]:m[1], m[2]:m[3]] += mask1

        for k in s1:
            area = (s1[k][0] - s1[k][1]) * (s1[k][2] - s1[k][3])
            if area > low_Tarea and area < up_Tarea:
                new_s[k] = [m[0] + s1[k][0], m[0] + s1[k][1], m[2] + s1[k][2], m[2] + s1[k][3]]
        max_index = max([max_index]+list(new_s))
    if dlog == 1: rm_detail.write("\tIn level 2 segmentation %d rejected\n\tTotal number of segments %d\n\tNumber of rejected segments %d\n"%(s2count,total,s1count+s2count))

    s.update(new_s)
    torg = org.copy()
    for i in s:
        imgRectangled = cv2.rectangle(torg, (s[i][2], s[i][0]), (s[i][3], s[i][1]), (0, 0, 255), 1)
    
    return segments, s, imgRectangled, mask
