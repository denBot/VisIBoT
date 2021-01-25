const { Schema, model } = require("mongoose")

const schema = new Schema({
  _id: String,
  occurrences: Number,
  data: Object,
  server_type: String,
  hostname: String,
  created_at: Date,
  updated_at: Date,
})

const IpGeoData = model("IpGeoData", schema, "ip_geo_data")

module.exports = IpGeoData
