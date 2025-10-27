from flask import Blueprint, render_template, request, redirect, url_for
from bson.objectid import ObjectId, InvalidId
from config import collection  # Import collection from config.py

# Create a Blueprint for the update functionality
update_bp = Blueprint('update', __name__)

@update_bp.route('/update/<id>', methods=['GET', 'POST'])
def update(id):
    try:
        # Determine if the ID is an ObjectId or a string
        try:
            object_id = ObjectId(id)
        except InvalidId:
            object_id = id  # Use as a string if not an ObjectId

        if request.method == 'POST':
            # Collect updated data from form
            update_data = {key: value for key, value in request.form.items() if key != '_id'}
            collection.update_one({"_id": object_id}, {"$set": update_data})
            return redirect(url_for('index'))

        # Fetch the document to pre-fill the form
        entry = collection.find_one({"_id": object_id})
        if not entry:
            return "Document not found", 404

        entry['_id'] = str(entry['_id'])  # Ensure _id is a string for template compatibility
        return render_template('update.html', entry=entry)

    except Exception as e:
        return str(e), 400
