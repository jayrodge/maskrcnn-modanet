import json
import os

with open(os.path.expanduser('~')+ '/.maskrcnn-modanet/' + 'savedvars.json') as f:
	savedvars = json.load(f)
path = savedvars['datapath']

img_path = path + "datasets/coco/images/"
ann_path = path + "datasets/coco/annotations/"
snp_path = path + "results/snapshots"


def get_session():
	import tensorflow as tf

	config = tf.ConfigProto()
	config.gpu_options.allow_growth = True
	return tf.Session(config=config)

def draw_mask_only(image, box, mask, label=None, color=None, binarize_threshold=0.5):
	""" Draws a mask in a given box and makes everything else black.
	Args
	    image              : Three dimensional image to draw on.
	    box                : Vector of at least 4 values (x1, y1, x2, y2) representing a box in the image.
	    mask               : A 2D float mask which will be reshaped to the size of the box, binarized and drawn over the image.
	    color              : Color to draw the mask with. If the box has 5 values, the last value is assumed to be the label and used to construct a default color.
	    binarize_threshold : Threshold used for binarizing the mask.
	"""

	from keras_retinanet.utils.colors import label_color

	# import miscellaneous modules
	import cv2
	import numpy as np


	if label is not None:
	    color = label_color(label)
	if color is None:
	    color = (0, 255, 0)

	# resize to fit the box
	mask = mask.astype(np.float32)
	mask = cv2.resize(mask, (box[2] - box[0], box[3] - box[1]))

	# binarize the mask
	mask = (mask > binarize_threshold).astype(np.uint8)

	# draw the mask in the image
	mask_image = np.zeros((image.shape[0], image.shape[1]), np.uint8)
	mask_image[box[1]:box[3], box[0]:box[2]] = mask
	mask = mask_image

	# compute a nice border around the mask
	border = mask - cv2.erode(mask, np.ones((5, 5), np.uint8), iterations=1)

	# apply color to the mask and border
	mask = (np.stack([mask] * 3, axis=2) * color).astype(np.uint8)
	border = (np.stack([border] * 3, axis=2) * (255, 255, 255)).astype(np.uint8)

	# this is how you look into the mask
	# for i in mask:
	# 	for j in i:
	# 		b = False
	# 		for k in i:
	# 			for l in k:
	# 				if l != 0:
	# 					b = True
	# 				if b:
	# 					break
	# 			if b:
	# 				break
	# 		if b:
	# 			print (j)

	# draw the mask
	indices = np.where(mask != color)
	image[indices[0], indices[1], :] = 0 * image[indices[0], indices[1], :]

def main(proc_img_path=None, proc_img_url=None, all_set=True, save_path=None, model_path=None, segments=False, annotations=False, threshold_score=0.5, limit=None):
	# import keras
	import keras

	# import keras_retinanet
	from keras_maskrcnn import models
	from keras_maskrcnn.utils.visualization import draw_mask
	from keras_retinanet.utils.visualization import draw_box, draw_caption, draw_annotations
	from keras_retinanet.utils.image import read_image_bgr, preprocess_image, resize_image
	from keras_retinanet.utils.colors import label_color

	# import miscellaneous modules
	import matplotlib.pyplot as plt
	import cv2
	import numpy as np
	import time

	# set tf backend to allow memory to grow, instead of claiming everything
	import tensorflow as tf

	# use this environment flag to change which GPU to use
	#os.environ["CUDA_VISIBLE_DEVICES"] = "1"

	# set the modified tf session as backend in keras
	keras.backend.tensorflow_backend.set_session(get_session())

	# adjust this to point to your trained model
	if not model_path:
		# get all models names in the results folder
		modelnames = [f for f in os.listdir(snp_path) if os.path.isfile(os.path.join(snp_path, f))]
		import re

		def extract_number(f):
		    s = re.findall("\d+$",f)
		    return (int(s[0]) if s else -1,f)
		# get the model name with the highest epoch
		print(max(modelnames,key=extract_number))
		model_path = os.path.join(snp_path, max(modelnames,key=extract_number))

	# load retinanet model
	model = models.load_model(model_path, backbone_name='resnet50')
	#print(model.summary())

	# load label to names mapping for visualization purposes
	labels_to_names = {0: 'bag', 1: 'belt', 2: 'boots', 3: 'footwear', 4: 'outer', 5: 'dress', 6: 'sunglasses', 7: 'pants', 8: 'top', 9: 'shorts', 10: 'skirt', 11: 'headwear', 12: 'scarf/tie'}

	default_save_path = False
	if save_path == 'default':
		# set path to default
		save_path = path + 'results/processedimages/'#images/1.jpg'
		if not annotations:
			save_path += 'images/'
		elif annotations:
			save_path += 'annotations/'
		default_save_path = True
	SAVE_PATH = save_path # used for multiple images

	if annotations:
		# if save_path: save_path = path + 'results/processedimages/annotations/1.json'
		annotations = [{
			'bbox': None,
			'score': None,
			'category': None,
			'part' : None
		}]


	if all_set:
		# load images
		with open(ann_path + 'instances_val.json') as f:
			instances = json.load(f)
		images = instances['images']
		for img in images:
			img['file_name']  = img_path + img['file_name']

	elif proc_img_path:
		# just draw the image selected
		images = [{'file_name': proc_img_path}]
	elif proc_img_url:
		# just draw the image selected
		images = [{'file_name': proc_img_url}]


	try:
		#for each image in the dataset
		for i, img in enumerate(images):
			print(i, end=' ')
			if limit and i >= limit:
				break

			if all_set:
				image = read_image_bgr(img['file_name'])
			elif proc_img_path:
				image = read_image_bgr(img['file_name'])
			elif proc_img_url:
				import requests
				from io import BytesIO
				r = requests.get(img['file_name'], allow_redirects=True)
				image = read_image_bgr(BytesIO(r.content))

			if default_save_path:
				if proc_img_path or all_set:
					img_file_name = img['file_name'].split("/")[-1]

				elif proc_img_url:
					img_file_name = 'urlimg.jpg'
				if not annotations:
					save_path += img_file_name
				elif annotations:
					save_path += img_file_name.split('.')[0] + '.json'
			if save_path and segments and not annotations:
				#remove the extension
				save_path = save_path.split('.')[0]


			# copy to draw on
			draw = image.copy()
			draw = cv2.cvtColor(draw, cv2.COLOR_BGR2RGB)

			# preprocess image for network
			image = preprocess_image(image)
			image, scale = resize_image(image)

			# process image
			start = time.time()
			outputs = model.predict_on_batch(np.expand_dims(image, axis=0))
			print("processing time: ", time.time() - start, "\t(Ctrl+c and close image to exit)")

			boxes  = outputs[-4][0]
			scores = outputs[-3][0]
			labels = outputs[-2][0]
			masks  = outputs[-1][0]

			# correct for image scale
			boxes /= scale

			if annotations:
				annotations = [{
								'bbox': None,
								'score': None,
								'category': None,
								'part' : None
				} for i in range(len([score for score in scores if score >= threshold_score]))]

			segment_id = 0
			# visualize detections
			for box, score, label, mask in zip(boxes, scores, labels, masks):
				if score < threshold_score:
					break
				color = label_color(label)

				if not segments:
					b = box.astype(int)
					draw_box(draw, b, color=color)

					mask = mask[:, :, label]
					draw_mask(draw, b, mask, color=label_color(label))

					caption = "{} {:.3f}".format(labels_to_names[label], score)
					draw_caption(draw, b, caption)
				elif segments:
					drawclone = np.copy(draw)

					b = box.astype(int)
					# draw_box(drawclone, b, color=color)

					mask = mask[:, :, label]
					draw_mask_only(drawclone, b, mask, color=label_color(label))
					
					if not annotations:
						caption = "{} {:.3f}".format(labels_to_names[label], score)
						draw_caption(drawclone, b, caption)
						plt.figure(figsize=(15, 15))
						plt.axis('off')
						plt.imshow(drawclone)
						if not save_path:
							plt.show()
						elif save_path:
							segment_path = '_segment_' + segment_id + '.jpg'
							save_path_segment = save_path + segment_path
							print(save_path_segment)
							plt.savefig(save_path_segment)
							plt.close()

					elif annotations:
						annotations[segment_id]['bbox'] = b
						annotations[segment_id]['score'] = score
						annotations[segment_id]['category'] = label
						annotations[segment_id]['part'] = drawclone # only the object inside the mask is shown, the rest is black
				segment_id += 1
						
			if not segments:    
				plt.figure(figsize=(15, 15))
				plt.axis('off')
				plt.imshow(draw)
				if not save_path:
					if not proc_img_url:
						print(img['file_name'])
					plt.show()
				elif save_path:
					print(save_path)
					plt.savefig(save_path)
					plt.close()
			elif segments:
				if annotations:
					if save_path:
						print(save_path)
						with open(save_path, 'w') as outfile:
							json.dump(annotations, outfile)
					else:
						return annotations
			save_path = SAVE_PATH # restore path for next image

	except KeyboardInterrupt:
		pass


def apply_mask(model, image, threshold_score=0.5):
	''' Process image numpy matrix using model and return the annotations '''



	from keras_retinanet.utils.image import preprocess_image, resize_image
	from keras_retinanet.utils.colors import label_color

	# import miscellaneous modules
	import numpy as np
	import time


	# load label to names mapping for visualization purposes
	labels_to_names = {0: 'bag', 1: 'belt', 2: 'boots', 3: 'footwear', 4: 'outer', 5: 'dress', 6: 'sunglasses', 7: 'pants', 8: 'top', 9: 'shorts', 10: 'skirt', 11: 'headwear', 12: 'scarf/tie'}

	# copy to draw on
	draw = image.copy()

	#switching to RGB from BGR
	draw[:, :, 2] = image[:, :, 0]
	draw[:, :, 0] = image[:, :, 2]

	# preprocess image for network
	image = preprocess_image(image)
	image, scale = resize_image(image)

	# process image
	start = time.time()
	outputs = model.predict_on_batch(np.expand_dims(image, axis=0))
	print("processing time: ", time.time() - start)

	boxes  = outputs[-4][0]
	scores = outputs[-3][0]
	labels = outputs[-2][0]
	masks  = outputs[-1][0]

	# correct for image scale
	boxes /= scale

	annotations = [{
					'bbox': None,
					'score': None,
					'category': None,
					'part' : None
	} for i in range(len([score for score in scores if score >= threshold_score]))]

	i = 0
	# visualize detections
	for box, score, label, mask in zip(boxes, scores, labels, masks):
		if score < threshold_score:
			break
		color = label_color(label)


		drawclone = np.copy(draw)

		b = box.astype(int)

		mask = mask[:, :, label]
		draw_mask_only(drawclone, b, mask, color=label_color(label))
		

		annotations[i]['bbox'] = b
		annotations[i]['score'] = score
		annotations[i]['category'] = label
		annotations[i]['part'] = drawclone # only the object inside the mask is shown, the rest is black
		i += 1


	return annotations